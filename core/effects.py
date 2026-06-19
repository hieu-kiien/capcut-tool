import pyJianYingDraft as draft

def apply_karaoke_to_segment(segment: draft.TextSegment, duration_us: int) -> None:
    """
    Applies CapCut's built-in Karaoke text animation to a TextSegment,
    with the animation duration matching the spoken/visible duration.
    """
    segment.add_animation(draft.TextIntro.卡拉OK, duration=duration_us)

def apply_karaoke_subtitles(script: draft.ScriptFile, track_name: str = "long_story_subtitles") -> int:
    """
    Iterates over all segments in a text track and applies karaoke text animations.
    """
    # Track selection
    track = script.tracks.get(track_name)
    if not track:
        return 0
        
    count = 0
    for segment in track.segments:
        if isinstance(segment, draft.TextSegment):
            apply_karaoke_to_segment(segment, segment.target_timerange.duration)
            count += 1
    return count
