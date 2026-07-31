import React from 'react';
import { Image as ImageIcon, FileText, Mic, Music, Sparkles, ShieldAlert } from 'lucide-react';
import { SubtitleItem, MediaAsset } from '../types';

interface TimelineProps {
  subtitles: SubtitleItem[];
  assets: MediaAsset[];
  playheadUs: number;
  totalDurationUs: number;
  setPlayheadUs: (us: number) => void;
}

export const Timeline: React.FC<TimelineProps> = ({
  subtitles,
  assets,
  playheadUs,
  totalDurationUs,
  setPlayheadUs,
}) => {
  const dur = totalDurationUs || 10_000_000;
  const playheadPercent = (playheadUs / dur) * 100;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-surface)', overflow: 'hidden' }}>
      {/* Timeline Ruler Header */}
      <div style={{ height: '28px', background: 'var(--bg-surface-header)', borderBottom: '1px solid var(--border-subtle)', position: 'relative', display: 'flex', alignItems: 'center', padding: '0 160px' }}>
        <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>00:00</div>
        <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', margin: '0 auto' }}>00:05</div>
        <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>00:10</div>
      </div>

      {/* Tracks Container */}
      <div style={{ flex: 1, overflowY: 'auto', position: 'relative', display: 'flex', flexDirection: 'column', gap: '4px', padding: '8px 0' }}>
        {/* Playhead Vertical Line */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: `calc(160px + ${playheadPercent}% * 0.8)`,
            width: '2px',
            background: 'var(--accent-cyan)',
            boxShadow: '0 0 8px var(--accent-cyan)',
            zIndex: 10,
            pointerEvents: 'none',
          }}
        />

        {/* Track 1: Logo Overlay */}
        <div style={{ display: 'flex', height: '36px', alignItems: 'center' }}>
          <div style={{ width: '160px', padding: '0 12px', fontSize: '11px', fontWeight: 600, color: 'var(--track-logo)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ShieldAlert size={14} /> Logo Track
          </div>
          <div style={{ flex: 1, background: 'var(--bg-surface-inset)', height: '100%', borderRadius: '4px', position: 'relative', border: '1px solid var(--border-subtle)' }}>
            <div style={{ position: 'absolute', left: '0%', width: '100%', height: '100%', background: 'rgba(245, 158, 11, 0.2)', border: '1px solid var(--track-logo)', borderRadius: '4px', padding: '4px 8px', fontSize: '10px', color: 'var(--track-logo)' }}>
              Watermark Logo
            </div>
          </div>
        </div>

        {/* Track 2: Animation Track */}
        <div style={{ display: 'flex', height: '36px', alignItems: 'center' }}>
          <div style={{ width: '160px', padding: '0 12px', fontSize: '11px', fontWeight: 600, color: 'var(--track-anim)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sparkles size={14} /> Animation
          </div>
          <div style={{ flex: 1, background: 'var(--bg-surface-inset)', height: '100%', borderRadius: '4px', position: 'relative', border: '1px solid var(--border-subtle)' }}>
            <div style={{ position: 'absolute', left: '10%', width: '30%', height: '100%', background: 'rgba(236, 72, 153, 0.2)', border: '1px solid var(--track-anim)', borderRadius: '4px', padding: '4px 8px', fontSize: '10px', color: 'var(--track-anim)' }}>
              Subscribe Overlay
            </div>
          </div>
        </div>

        {/* Track 3: Subtitle Track */}
        <div style={{ display: 'flex', height: '36px', alignItems: 'center' }}>
          <div style={{ width: '160px', padding: '0 12px', fontSize: '11px', fontWeight: 600, color: 'var(--track-srt)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <FileText size={14} /> Subtitles (SRT)
          </div>
          <div style={{ flex: 1, background: 'var(--bg-surface-inset)', height: '100%', borderRadius: '4px', position: 'relative', border: '1px solid var(--border-subtle)', display: 'flex', gap: '2px', padding: '2px' }}>
            {subtitles.map((sub) => {
              const leftPct = (sub.start_us / dur) * 100;
              const widthPct = ((sub.end_us - sub.start_us) / dur) * 100;
              return (
                <div
                  key={sub.id}
                  style={{
                    position: 'absolute',
                    left: `${leftPct}%`,
                    width: `${widthPct}%`,
                    height: 'calc(100% - 4px)',
                    background: 'rgba(0, 242, 254, 0.25)',
                    border: '1px solid var(--track-srt)',
                    borderRadius: '3px',
                    padding: '2px 4px',
                    fontSize: '9px',
                    color: '#fff',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {sub.text}
                </div>
              );
            })}
          </div>
        </div>

        {/* Track 4: Background Video Track (With Keyframe Diamonds) */}
        <div style={{ display: 'flex', height: '44px', alignItems: 'center' }}>
          <div style={{ width: '160px', padding: '0 12px', fontSize: '11px', fontWeight: 600, color: 'var(--track-video)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ImageIcon size={14} /> Video Clips
          </div>
          <div style={{ flex: 1, background: 'var(--bg-surface-inset)', height: '100%', borderRadius: '4px', position: 'relative', border: '1px solid var(--border-subtle)' }}>
            <div style={{ position: 'absolute', left: '0%', width: '100%', height: '100%', background: 'rgba(59, 130, 246, 0.25)', border: '1px solid var(--track-video)', borderRadius: '4px', padding: '4px 8px', fontSize: '10px', color: '#fff', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Background_Media_Sequence</span>

              {/* Keyframe Diamond Indicators */}
              <div style={{ display: 'flex', gap: '80px', paddingRight: '8px' }}>
                <div style={{ width: '8px', height: '8px', background: 'var(--accent-cyan)', transform: 'rotate(45deg)', boxShadow: '0 0 6px var(--accent-cyan)' }} />
                <div style={{ width: '8px', height: '8px', background: 'var(--accent-violet)', transform: 'rotate(45deg)', boxShadow: '0 0 6px var(--accent-violet)' }} />
              </div>
            </div>
          </div>
        </div>

        {/* Track 5: Voice Track */}
        <div style={{ display: 'flex', height: '36px', alignItems: 'center' }}>
          <div style={{ width: '160px', padding: '0 12px', fontSize: '11px', fontWeight: 600, color: 'var(--track-voice)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Mic size={14} /> Voice Narration
          </div>
          <div style={{ flex: 1, background: 'var(--bg-surface-inset)', height: '100%', borderRadius: '4px', position: 'relative', border: '1px solid var(--border-subtle)' }}>
            <div style={{ position: 'absolute', left: '0%', width: '100%', height: '100%', background: 'rgba(16, 185, 129, 0.2)', border: '1px solid var(--track-voice)', borderRadius: '4px', padding: '4px 8px', fontSize: '10px', color: 'var(--track-voice)' }}>
              Main Voice Audio Waveform
            </div>
          </div>
        </div>

        {/* Track 6: BGM Track */}
        <div style={{ display: 'flex', height: '36px', alignItems: 'center' }}>
          <div style={{ width: '160px', padding: '0 12px', fontSize: '11px', fontWeight: 600, color: 'var(--track-bgm)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Music size={14} /> BGM Music
          </div>
          <div style={{ flex: 1, background: 'var(--bg-surface-inset)', height: '100%', borderRadius: '4px', position: 'relative', border: '1px solid var(--border-subtle)' }}>
            <div style={{ position: 'absolute', left: '0%', width: '100%', height: '100%', background: 'rgba(139, 92, 246, 0.2)', border: '1px solid var(--track-bgm)', borderRadius: '4px', padding: '4px 8px', fontSize: '10px', color: 'var(--track-bgm)' }}>
              Background Music Loop
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
