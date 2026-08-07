"""REST endpoints for the Creator AI Assistant."""

from __future__ import annotations

import logging

from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .services import (
    audio_generator,
    gemini,
    idea_analyzer,
    language as lang_service,
    overview_simplifier,
    rails_publish,
    script_generator,
    structure_generator,
    verse_summary,
    webuddhist_plan,
)
from .services.ideas import IDEAS
from .services.content_loader import (
    ContentError,
    ContentUnavailableError,
    get_day_content,
    released_progress,
)

logger = logging.getLogger(__name__)

# Input caps to bound LLM/TTS cost and disk usage from client-supplied text.
MAX_CREATOR_NOTES = 2000
MAX_SCRIPT_CHARS = 5000
MAX_FEEDBACK = 1000
MAX_PUBLISH_CONTENT_CHARS = 20000

# Shown when GitHub itself is erroring/rate-limited rather than the content being missing.
CONTENT_UNAVAILABLE_MESSAGE = (
    "Content source is temporarily unavailable. Please try again in a moment."
)


class GenerateRateThrottle(AnonRateThrottle):
    """Stricter throttle for the expensive Gemini-backed generation endpoints."""

    scope = "generate"


def _auto_publish(*, dc, idea_key, focus_label, duration, language, output_type, content):
    """Push a freshly generated result to rails. Best-effort.

    Deliberately never raises: a GitHub hiccup, a rate limit, or a missing
    token must not fail a generation the creator already paid for and is
    waiting on. Returns the rails URL, or None if it couldn't be published (the
    client then offers a manual retry).
    """
    if not rails_publish.is_configured():
        return None
    try:
        return rails_publish.publish(
            day=dc.day, verses_label=dc.verses_label, idea_key=idea_key,
            focus_label=focus_label, duration_seconds=duration, language=language,
            output_type=output_type, content=content,
        )["url"]
    except Exception:
        logger.warning(
            "Auto-publish to rails failed (day=%s, idea=%s)",
            dc.day, idea_key, exc_info=True,
        )
        return None


@api_view(["GET"])
def health(request):
    payload = {
        "status": "ok",
        "gemini_configured": gemini.is_configured(),
    }
    try:
        payload["progress"] = released_progress()
    except ContentError:
        payload["progress"] = None
    return Response(payload)


@api_view(["GET"])
@throttle_classes([GenerateRateThrottle])
def day_detail(request, day: int):
    """Load a day's verses/plan and the video ideas its content supports.

    Throttled at the strict 'generate' rate (not the looser 'anon' rate) because
    a cache-miss here triggers a paid Gemini call via idea_analyzer.analyze.
    """
    language = lang_service.normalize(request.query_params.get("language"))
    try:
        dc = get_day_content(day)
    except ContentUnavailableError:
        logger.warning("Day content temporarily unavailable (day=%s)", day, exc_info=True)
        return Response({"error": CONTENT_UNAVAILABLE_MESSAGE},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except ContentError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    # Pair each verse text with its verse number (e.g. "1-6" -> "6") and full id
    # (so the client can look up that verse's resources in `verseResources`).
    # Best-effort: use schedule IDs for as many texts as available; leave extras blank.
    verse_lines = [
        {
            "id": dc.verses[i] if i < len(dc.verses) else "",
            "n": dc.verses[i].split("-")[-1] if i < len(dc.verses) else "",
            "text": t,
        }
        for i, t in enumerate(dc.verses_text)
    ]

    # Rewrite each verse's "AI Overview" blurb into plainer language — in the
    # selected language (Hindi is explained in Hindi), cached per day+language.
    # Degrades to the original text on any failure, so this never breaks the day.
    try:
        simplified = overview_simplifier.simplify(dc, language)
        for vid, text in simplified.items():
            if vid in dc.verse_resources:
                dc.verse_resources[vid]["commentary_overview"] = text
    except Exception:
        logger.warning("Overview simplify failed (day=%s)", day, exc_info=True)

    # The per-day share link is built from config alone (no network call), so a
    # failure here should never break loading the day — degrade to no link.
    try:
        share_url = webuddhist_plan.share_url(dc.day, language)
    except webuddhist_plan.PlanShareError:
        logger.warning("Could not build share link (day=%s)", day, exc_info=True)
        share_url = None

    return Response({
        "day": dc.day,
        "verses": dc.verses,
        "versesLabel": dc.verses_label,
        "date": dc.date,
        "verseText": dc.verse_block,
        "verseLines": verse_lines,
        "verseResources": dc.verse_resources,
        "planFile": dc.plan_file,
        "isVariant": dc.is_variant,
        "availableIdeas": idea_analyzer.available_ideas(dc, language),
        "shareUrl": share_url,
    })


@api_view(["GET"])
def day_share_image(request, day: int):
    """Proxy the 'today's challenge' shareable image for a day.

    The upstream plan API and its S3 bucket send no CORS headers and the S3 URL
    is presigned (expires ~1h), so the browser can't use either directly. We
    resolve the image server-side and stream the bytes back same-origin, which
    lets the frontend both display it (<img>) and blob-download it. Not on the
    strict 'generate' throttle — it makes no paid Gemini call.
    """
    language = lang_service.normalize(request.query_params.get("language"))
    try:
        url = webuddhist_plan.shareable_image_url(day, language)
        if not url:
            return Response({"error": "No shareable image for this day."},
                            status=status.HTTP_404_NOT_FOUND)
        content, content_type = webuddhist_plan.fetch_image(url)
    except webuddhist_plan.PlanShareUnavailable:
        logger.warning("Share image temporarily unavailable (day=%s)", day, exc_info=True)
        return Response({"error": CONTENT_UNAVAILABLE_MESSAGE},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except webuddhist_plan.PlanShareError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    resp = HttpResponse(content, content_type=content_type)
    # Safe to cache: the image for a given day is stable even though the signed
    # upstream URL rotates.
    resp["Cache-Control"] = "public, max-age=900"
    return resp


@api_view(["POST"])
@throttle_classes([GenerateRateThrottle])
def verse_summary_view(request):
    """Generate a simple bullet-point summary of a day's verses in a language."""
    data = request.data or {}
    day = data.get("day")
    language = (data.get("language") or "english").lower()

    if day is None:
        return Response({"error": "day is required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        day = int(day)
    except (TypeError, ValueError):
        return Response({"error": "day must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

    if language not in verse_summary.LANGUAGES:
        return Response(
            {"error": "language must be 'english' or 'hindi'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        dc = get_day_content(day)
    except ContentUnavailableError:
        logger.warning("Day content temporarily unavailable (day=%s)", day, exc_info=True)
        return Response({"error": CONTENT_UNAVAILABLE_MESSAGE},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except ContentError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    try:
        points = verse_summary.summarize(dc, language)
    except gemini.GeminiNotConfigured as exc:
        return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        logger.exception("Verse summary failed (day=%s, lang=%s)", day, language)
        return Response({"error": "Could not summarize the verses. Please try again."},
                        status=status.HTTP_502_BAD_GATEWAY)

    return Response({"day": dc.day, "language": language, "points": points})


@api_view(["POST"])
@throttle_classes([GenerateRateThrottle])
def generate_script(request):
    data = request.data or {}
    day = data.get("day")
    idea_key = data.get("ideaKey")
    duration = data.get("durationSeconds")
    creator_notes = data.get("creatorNotes", "") or ""
    feedback = data.get("feedback", "") or ""
    previous = data.get("previous", "") or ""
    language = lang_service.normalize(data.get("language"))
    focus = (data.get("focus") or "")[:MAX_CREATOR_NOTES]
    focus_label = (data.get("focusLabel") or "")[:80]

    if day is None or idea_key is None or duration is None:
        return Response(
            {"error": "day, ideaKey, and durationSeconds are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        day = int(day)
        duration = int(duration)
    except (TypeError, ValueError):
        return Response({"error": "day and durationSeconds must be integers."},
                        status=status.HTTP_400_BAD_REQUEST)

    if len(creator_notes) > MAX_CREATOR_NOTES:
        return Response(
            {"error": f"creatorNotes is too long (max {MAX_CREATOR_NOTES} characters)."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(feedback) > MAX_FEEDBACK:
        return Response(
            {"error": f"feedback is too long (max {MAX_FEEDBACK} characters)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        dc = get_day_content(day)
    except ContentUnavailableError:
        logger.warning("Day content temporarily unavailable (day=%s)", day, exc_info=True)
        return Response({"error": CONTENT_UNAVAILABLE_MESSAGE},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except ContentError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    try:
        script = script_generator.generate(
            dc, idea_key, duration, creator_notes,
            feedback=feedback, previous=str(previous), language=language,
            focus=focus, focus_label=focus_label,
        )
    except gemini.GeminiNotConfigured as exc:
        return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        logger.exception("Script generation failed (day=%s, idea=%s)", day, idea_key)
        return Response({"error": "Script generation failed. Please try again."},
                        status=status.HTTP_502_BAD_GATEWAY)

    rails_url = _auto_publish(
        dc=dc, idea_key=idea_key, focus_label=focus_label, duration=duration,
        language=language, output_type="script", content=script,
    )

    return Response({
        "day": dc.day,
        "ideaKey": idea_key,
        "durationSeconds": duration,
        "targetWords": script_generator.target_words(duration),
        "script": script,
        "railsUrl": rails_url,
    })


@api_view(["POST"])
@throttle_classes([GenerateRateThrottle])
def generate_structure(request):
    data = request.data or {}
    day = data.get("day")
    idea_key = data.get("ideaKey")
    duration = data.get("durationSeconds")
    creator_notes = data.get("creatorNotes", "") or ""
    feedback = data.get("feedback", "") or ""
    previous = data.get("previous") or None
    language = lang_service.normalize(data.get("language"))
    focus = (data.get("focus") or "")[:MAX_CREATOR_NOTES]
    focus_label = (data.get("focusLabel") or "")[:80]

    if day is None or idea_key is None or duration is None:
        return Response(
            {"error": "day, ideaKey, and durationSeconds are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        day = int(day)
        duration = int(duration)
    except (TypeError, ValueError):
        return Response({"error": "day and durationSeconds must be integers."},
                        status=status.HTTP_400_BAD_REQUEST)

    if len(creator_notes) > MAX_CREATOR_NOTES:
        return Response(
            {"error": f"creatorNotes is too long (max {MAX_CREATOR_NOTES} characters)."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(feedback) > MAX_FEEDBACK:
        return Response(
            {"error": f"feedback is too long (max {MAX_FEEDBACK} characters)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        dc = get_day_content(day)
    except ContentUnavailableError:
        logger.warning("Day content temporarily unavailable (day=%s)", day, exc_info=True)
        return Response({"error": CONTENT_UNAVAILABLE_MESSAGE},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except ContentError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    try:
        structure = structure_generator.generate(
            dc, idea_key, duration, creator_notes,
            feedback=feedback, previous=previous if isinstance(previous, dict) else None,
            language=language, focus=focus, focus_label=focus_label,
        )
    except gemini.GeminiNotConfigured as exc:
        return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        logger.exception("Structure generation failed (day=%s, idea=%s)", day, idea_key)
        return Response({"error": "Structure generation failed. Please try again."},
                        status=status.HTTP_502_BAD_GATEWAY)

    return Response({
        "day": dc.day,
        "ideaKey": idea_key,
        "durationSeconds": duration,
        "structure": structure,
        "railsUrl": _auto_publish(
            dc=dc, idea_key=idea_key, focus_label=focus_label, duration=duration,
            language=language, output_type="structure", content=structure,
        ),
    })


@api_view(["POST"])
@throttle_classes([GenerateRateThrottle])
def generate_audio(request):
    data = request.data or {}
    script = (data.get("script") or "").strip()
    voice = data.get("voice") or None

    if not script:
        return Response({"error": "script is required."}, status=status.HTTP_400_BAD_REQUEST)
    if len(script) > MAX_SCRIPT_CHARS:
        return Response(
            {"error": f"script is too long (max {MAX_SCRIPT_CHARS} characters)."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if voice is not None and voice not in settings.GEMINI_TTS_VOICES_ALLOWED:
        return Response({"error": "Unsupported voice."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        audio_url = audio_generator.generate(script, voice=voice)
    except gemini.GeminiNotConfigured as exc:
        return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception:
        logger.exception("Audio generation failed")
        return Response({"error": "Audio generation failed. Please try again."},
                        status=status.HTTP_502_BAD_GATEWAY)

    return Response({"audioUrl": request.build_absolute_uri(audio_url)})


@api_view(["POST"])
@throttle_classes([GenerateRateThrottle])
def publish_generated(request):
    """Publish a generated script/structure to rails — manual retry path.

    Generation already auto-publishes (see `_auto_publish`), so this exists for
    the case where that best-effort push failed (GitHub down, rate-limited) and
    the client offers a retry. Publishing the same (day, idea, focus, duration,
    language) updates that file in place, so git's commit history becomes the
    version trail.
    """
    if not rails_publish.is_configured():
        return Response(
            {"error": "Publishing to rails isn't configured on this server."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    data = request.data or {}
    day = data.get("day")
    idea_key = data.get("ideaKey")
    duration = data.get("durationSeconds")
    language = lang_service.normalize(data.get("language"))
    output_type = data.get("outputType")
    focus_label = (data.get("focusLabel") or "")[:80]
    content = data.get("content")

    if day is None or idea_key is None or duration is None or output_type is None or content is None:
        return Response(
            {"error": "day, ideaKey, durationSeconds, outputType, and content are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if idea_key not in IDEAS:
        return Response({"error": "Unknown ideaKey."}, status=status.HTTP_400_BAD_REQUEST)
    if output_type not in ("script", "structure"):
        return Response({"error": "outputType must be 'script' or 'structure'."},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        day = int(day)
        duration = int(duration)
    except (TypeError, ValueError):
        return Response({"error": "day and durationSeconds must be integers."},
                        status=status.HTTP_400_BAD_REQUEST)

    if output_type == "script":
        if not isinstance(content, str) or not content.strip():
            return Response({"error": "content must be a non-empty string for a script."},
                            status=status.HTTP_400_BAD_REQUEST)
        if len(content) > MAX_PUBLISH_CONTENT_CHARS:
            return Response({"error": "content is too long."}, status=status.HTTP_400_BAD_REQUEST)
    else:
        if not isinstance(content, dict):
            return Response({"error": "content must be a structure object."},
                            status=status.HTTP_400_BAD_REQUEST)

    try:
        dc = get_day_content(day)
    except ContentUnavailableError:
        logger.warning("Day content temporarily unavailable (day=%s)", day, exc_info=True)
        return Response({"error": CONTENT_UNAVAILABLE_MESSAGE},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except ContentError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    try:
        result = rails_publish.publish(
            day=dc.day, verses_label=dc.verses_label, idea_key=idea_key,
            focus_label=focus_label, duration_seconds=duration, language=language,
            output_type=output_type, content=content,
        )
    except rails_publish.PublishError:
        logger.exception("Review publish failed (day=%s, idea=%s)", day, idea_key)
        return Response({"error": "Could not publish to rails. Please try again."},
                        status=status.HTTP_502_BAD_GATEWAY)

    return Response({"url": result["url"]})
