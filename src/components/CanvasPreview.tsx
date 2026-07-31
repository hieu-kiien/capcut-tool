import React, { useEffect, useRef, useState } from 'react';
import { Play, Pause, SkipBack, SkipForward, Monitor, Smartphone, Square } from 'lucide-react';
import { WebGLPreviewRenderer } from '../engine/webgl_renderer';

interface CanvasPreviewProps {
  aspectRatio: '16:9' | '9:16' | '1:1';
  setAspectRatio: (r: '16:9' | '9:16' | '1:1') => void;
  playheadUs: number;
  setPlayheadUs: (us: number) => void;
  totalDurationUs: number;
}

export const CanvasPreview: React.FC<CanvasPreviewProps> = ({
  aspectRatio,
  setAspectRatio,
  playheadUs,
  setPlayheadUs,
  totalDurationUs,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const rendererRef = useRef<WebGLPreviewRenderer | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    if (canvasRef.current && !rendererRef.current) {
      rendererRef.current = new WebGLPreviewRenderer(canvasRef.current);
    }
  }, []);

  useEffect(() => {
    if (rendererRef.current) {
      // Simulate live Keyframe Zoom in transform (Scale: 1.0 -> 1.15)
      const progress = playheadUs / (totalDurationUs || 1);
      const currentScale = 1.0 + progress * 0.15;
      rendererRef.current.renderFrame(playheadUs, {
        scale: currentScale,
        posX: 0,
        posY: 0,
        rotation: 0,
        alpha: 1.0,
      });
    }
  }, [playheadUs, totalDurationUs]);

  const togglePlay = () => {
    if (!rendererRef.current) return;
    if (isPlaying) {
      rendererRef.current.stopLoop();
      setIsPlaying(false);
    } else {
      rendererRef.current.startLoop((us) => {
        setPlayheadUs(us);
      });
      setIsPlaying(true);
    }
  };

  const formatTimecode = (us: number) => {
    const totalSec = Math.floor(us / 1000000);
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    const ms = Math.floor((us % 1000000) / 1000);
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
  };

  const getCanvasDimensions = () => {
    if (aspectRatio === '9:16') return { width: 270, height: 480 };
    if (aspectRatio === '1:1') return { width: 420, height: 420 };
    return { width: 560, height: 315 }; // 16:9
  };

  const dims = getCanvasDimensions();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-obsidian)', borderBottom: '1px solid var(--border-subtle)' }}>
      {/* Top Viewport Header */}
      <div style={{ padding: '8px 16px', background: 'var(--bg-surface-header)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>Live Canvas Preview (WebGL 60fps)</span>
          <span style={{ fontSize: '10px', padding: '2px 6px', background: 'var(--bg-surface-inset)', border: '1px solid var(--border-subtle)', borderRadius: '4px', color: 'var(--accent-cyan)' }}>
            {aspectRatio}
          </span>
        </div>

        {/* Aspect Ratio Selector */}
        <div style={{ display: 'flex', gap: '4px' }}>
          <button
            onClick={() => setAspectRatio('16:9')}
            style={{
              padding: '4px 8px',
              background: aspectRatio === '16:9' ? 'var(--bg-surface-elevated)' : 'transparent',
              border: aspectRatio === '16:9' ? '1px solid var(--accent-cyan)' : '1px solid transparent',
              borderRadius: '4px',
              color: aspectRatio === '16:9' ? 'var(--accent-cyan)' : 'var(--text-muted)',
              fontSize: '11px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <Monitor size={12} /> 16:9
          </button>
          <button
            onClick={() => setAspectRatio('9:16')}
            style={{
              padding: '4px 8px',
              background: aspectRatio === '9:16' ? 'var(--bg-surface-elevated)' : 'transparent',
              border: aspectRatio === '9:16' ? '1px solid var(--accent-cyan)' : '1px solid transparent',
              borderRadius: '4px',
              color: aspectRatio === '9:16' ? 'var(--accent-cyan)' : 'var(--text-muted)',
              fontSize: '11px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <Smartphone size={12} /> 9:16
          </button>
          <button
            onClick={() => setAspectRatio('1:1')}
            style={{
              padding: '4px 8px',
              background: aspectRatio === '1:1' ? 'var(--bg-surface-elevated)' : 'transparent',
              border: aspectRatio === '1:1' ? '1px solid var(--accent-cyan)' : '1px solid transparent',
              borderRadius: '4px',
              color: aspectRatio === '1:1' ? 'var(--accent-cyan)' : 'var(--text-muted)',
              fontSize: '11px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <Square size={12} /> 1:1
          </button>
        </div>
      </div>

      {/* Canvas Viewport Area */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', overflow: 'hidden', padding: '16px' }}>
        <canvas
          ref={canvasRef}
          width={dims.width}
          height={dims.height}
          style={{
            borderRadius: '8px',
            boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
            border: '1px solid var(--border-medium)',
          }}
        />
      </div>

      {/* Scrub & Playback Controls Bar */}
      <div style={{ padding: '8px 16px', background: 'var(--bg-surface-header)', display: 'flex', alignItems: 'center', gap: '16px', borderTop: '1px solid var(--border-subtle)' }}>
        <button
          onClick={togglePlay}
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            background: 'var(--accent-gradient)',
            border: 'none',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
          }}
        >
          {isPlaying ? <Pause size={16} /> : <Play size={16} style={{ marginLeft: '2px' }} />}
        </button>

        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--accent-cyan)', width: '110px' }}>
          {formatTimecode(playheadUs)}
        </span>

        <input
          type="range"
          min={0}
          max={totalDurationUs || 10000000}
          value={playheadUs}
          onChange={(e) => setPlayheadUs(Number(e.target.value))}
          style={{
            flex: 1,
            accentColor: 'var(--accent-cyan)',
            cursor: 'pointer',
          }}
        />

        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)' }}>
          {formatTimecode(totalDurationUs)}
        </span>
      </div>
    </div>
  );
};
