"""REST endpoints for the Creator AI Assistant."""

from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .services import audio_generator, gemini, idea_analyzer, script_generator
from .services.content_loader import ContentError, get_day_content


@api_view(["GET"])
def health(request):
    return Response({
        "status": "ok",
        "gemini_configured": gemini.is_configured(),
    })


@api_view(["GET"])
def day_detail(request, day: int):
    """Load a day's verses/plan and the video ideas its content supports."""
    try:
        dc = get_day_content(day)
    except ContentError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        "day": dc.day,
        "verses": dc.verses,
        "versesLabel": dc.verses_label,
        "date": dc.date,
        "planFile": dc.plan_file,
        "isVariant": dc.is_variant,
        "availableIdeas": idea_analyzer.available_ideas(dc),
    })


@api_view(["POST"])
def generate_script(request):
    data = request.data or {}
    day = data.get("day")
    idea_key = data.get("ideaKey")
    duration = data.get("durationSeconds")
    creator_notes = data.get("creatorNotes", "") or ""

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

    try:
        dc = get_day_content(day)
    except ContentError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    try:
        script = script_generator.generate(dc, idea_key, duration, creator_notes)
    except gemini.GeminiNotConfigured as exc:
        return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:  # surface upstream LLM errors cleanly
        return Response({"error": f"Script generation failed: {exc}"},
                        status=status.HTTP_502_BAD_GATEWAY)

    return Response({
        "day": dc.day,
        "ideaKey": idea_key,
        "durationSeconds": duration,
        "targetWords": script_generator.target_words(duration),
        "script": script,
    })


@api_view(["POST"])
def generate_audio(request):
    data = request.data or {}
    script = (data.get("script") or "").strip()
    voice = data.get("voice") or None

    if not script:
        return Response({"error": "script is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        audio_url = audio_generator.generate(script, voice=voice)
    except gemini.GeminiNotConfigured as exc:
        return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as exc:
        return Response({"error": f"Audio generation failed: {exc}"},
                        status=status.HTTP_502_BAD_GATEWAY)

    return Response({"audioUrl": request.build_absolute_uri(audio_url)})
