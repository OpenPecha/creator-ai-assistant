"""REST endpoints for the Creator AI Assistant."""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .services import (
    audio_generator,
    gemini,
    idea_analyzer,
    language as lang_service,
    script_generator,
    structure_generator,
    verse_summary,
)
from .services.content_loader import ContentError, get_day_content, released_progress

logger = logging.getLogger(__name__)

# Input caps to bound LLM/TTS cost and disk usage from client-supplied text.
MAX_CREATOR_NOTES = 2000
MAX_SCRIPT_CHARS = 5000
MAX_FEEDBACK = 1000


class GenerateRateThrottle(AnonRateThrottle):
    """Stricter throttle for the expensive Gemini-backed generation endpoints."""

    scope = "generate"


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
def day_detail(request, day: int):
    """Load a day's verses/plan and the video ideas its content supports."""
    language = lang_service.normalize(request.query_params.get("language"))
    try:
        dc = get_day_content(day)
    except ContentError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    # Pair each verse text with its verse number (e.g. "1-6" -> "6").
    # Best-effort: use schedule IDs for as many texts as available; leave extras blank.
    verse_lines = [
        {"n": dc.verses[i].split("-")[-1] if i < len(dc.verses) else "", "text": t}
        for i, t in enumerate(dc.verses_text)
    ]

    return Response({
        "day": dc.day,
        "verses": dc.verses,
        "versesLabel": dc.verses_label,
        "date": dc.date,
        "verseText": dc.verse_block,
        "verseLines": verse_lines,
        "planFile": dc.plan_file,
        "isVariant": dc.is_variant,
        "availableIdeas": idea_analyzer.available_ideas(dc, language),
    })


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
    except Exception:  # log details server-side, return a generic message
        logger.exception("Script generation failed (day=%s, idea=%s)", day, idea_key)
        return Response({"error": "Script generation failed. Please try again."},
                        status=status.HTTP_502_BAD_GATEWAY)

    return Response({
        "day": dc.day,
        "ideaKey": idea_key,
        "durationSeconds": duration,
        "targetWords": script_generator.target_words(duration),
        "script": script,
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

    try:
        audio_url = audio_generator.generate(script, voice=voice)
    except gemini.GeminiNotConfigured as exc:
        return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception:  # log details server-side, return a generic message
        logger.exception("Audio generation failed")
        return Response({"error": "Audio generation failed. Please try again."},
                        status=status.HTTP_502_BAD_GATEWAY)

    return Response({"audioUrl": request.build_absolute_uri(audio_url)})
