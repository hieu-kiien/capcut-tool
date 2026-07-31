import React, { useState } from 'react';
import { Download, Sliders, Layers, Sparkles, CheckCircle2, AlertCircle } from 'lucide-react';
import { ExportConfig } from '../types';

interface InspectorProps {
  exportConfig: ExportConfig;
  setExportConfig: React.Dispatch<React.SetStateAction<ExportConfig>>;
  onExport: () => void;
  isExporting: boolean;
  exportResult: { success: boolean; path: string; timeMs: number } | null;
}

export const Inspector: React.FC<InspectorProps> = ({
  exportConfig,
  setExportConfig,
  onExport,
  isExporting,
  exportResult,
}) => {
  const [selectedPreset, setSelectedPreset] = useState<'zoom_in' | 'zoom_out' | 'pan_left' | 'ken_burns'>('zoom_in');
  const [transition, setTransition] = useState<'mix' | 'fade' | 'slide'>('mix');

  return (
    <div className="studio-panel-right" style={{ height: '100%' }}>
      {/* Header */}
      <div style={{ padding: '12px 16px', background: 'var(--bg-surface-header)', borderBottom: '1px solid var(--border-subtle)', fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Sliders size={16} color="var(--accent-cyan)" /> Presets & Inspector
      </div>

      <div style={{ flex: 1, padding: '16px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Section 1: Motion Presets */}
        <div>
          <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '8px' }}>
            Preset Keyframe Zoom / Pan
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <button
              onClick={() => setSelectedPreset('zoom_in')}
              style={{
                padding: '10px',
                background: selectedPreset === 'zoom_in' ? 'var(--bg-surface-elevated)' : 'var(--bg-surface-inset)',
                border: selectedPreset === 'zoom_in' ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                borderRadius: '6px',
                color: selectedPreset === 'zoom_in' ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              Zoom In Chậm (1.0 → 1.15)
            </button>
            <button
              onClick={() => setSelectedPreset('zoom_out')}
              style={{
                padding: '10px',
                background: selectedPreset === 'zoom_out' ? 'var(--bg-surface-elevated)' : 'var(--bg-surface-inset)',
                border: selectedPreset === 'zoom_out' ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                borderRadius: '6px',
                color: selectedPreset === 'zoom_out' ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              Zoom Out Chậm (1.15 → 1.0)
            </button>
            <button
              onClick={() => setSelectedPreset('pan_left')}
              style={{
                padding: '10px',
                background: selectedPreset === 'pan_left' ? 'var(--bg-surface-elevated)' : 'var(--bg-surface-inset)',
                border: selectedPreset === 'pan_left' ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                borderRadius: '6px',
                color: selectedPreset === 'pan_left' ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              Trượt Trái (Pan Left)
            </button>
            <button
              onClick={() => setSelectedPreset('ken_burns')}
              style={{
                padding: '10px',
                background: selectedPreset === 'ken_burns' ? 'var(--bg-surface-elevated)' : 'var(--bg-surface-inset)',
                border: selectedPreset === 'ken_burns' ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                borderRadius: '6px',
                color: selectedPreset === 'ken_burns' ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              Ken Burns Nảy Nhẹ
            </button>
          </div>
        </div>

        {/* Section 2: Transition Selector */}
        <div>
          <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '8px' }}>
            Hiệu Ứng Chuyển Cảnh (Transitions)
          </label>
          <select
            value={transition}
            onChange={(e) => setTransition(e.target.value as any)}
            style={{
              width: '100%',
              padding: '8px 12px',
              background: 'var(--bg-surface-inset)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '6px',
              color: 'var(--text-primary)',
              fontSize: '12px',
            }}
          >
            <option value="mix">Mix Crossfade (Hòa trộn mượt)</option>
            <option value="fade">Central Fade (Mờ đen trung tâm)</option>
            <option value="slide">Slide Left (Trượt sang trái)</option>
          </select>
        </div>

        {/* Section 3: CapCut PC Export Config */}
        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
          <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
            Tên Dự Án CapCut
          </label>
          <input
            type="text"
            value={exportConfig.projectName}
            onChange={(e) => setExportConfig((prev) => ({ ...prev, projectName: e.target.value }))}
            style={{
              width: '100%',
              padding: '8px 12px',
              background: 'var(--bg-surface-inset)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '6px',
              color: 'var(--text-primary)',
              fontSize: '12px',
              marginBottom: '12px',
            }}
          />

          <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
            Thư Mục Lưu Dự Án CapCut
          </label>
          <input
            type="text"
            value={exportConfig.draftRoot}
            onChange={(e) => setExportConfig((prev) => ({ ...prev, draftRoot: e.target.value }))}
            style={{
              width: '100%',
              padding: '8px 12px',
              background: 'var(--bg-surface-inset)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '6px',
              color: 'var(--text-primary)',
              fontSize: '12px',
              marginBottom: '12px',
            }}
          />

          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
            <input
              type="checkbox"
              checked={exportConfig.isCompact}
              onChange={(e) => setExportConfig((prev) => ({ ...prev, isCompact: e.target.checked }))}
            />
            Xuất file Compact JSON (Tối ưu 40% dung lượng)
          </label>

          <button
            onClick={onExport}
            disabled={isExporting}
            className="btn-primary"
            style={{ width: '100%', padding: '12px', fontSize: '13px' }}
          >
            {isExporting ? (
              <span>Đang Ghi Dự Án...</span>
            ) : (
              <>
                <Download size={16} /> Tạo Dự Án CapCut PC
              </>
            )}
          </button>

          {exportResult && (
            <div
              style={{
                marginTop: '12px',
                padding: '10px 12px',
                background: exportResult.success ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                border: exportResult.success ? '1px solid var(--track-voice)' : '1px solid #EF4444',
                borderRadius: '6px',
                fontSize: '11px',
                color: exportResult.success ? 'var(--track-voice)' : '#EF4444',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              {exportResult.success ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
              <div>
                <div style={{ fontWeight: 600 }}>Tạo Draft Thành Công! ({exportResult.timeMs}ms)</div>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{exportResult.path}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
