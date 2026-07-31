import React, { useState, useEffect } from 'react';
import { AssetPool } from './components/AssetPool';
import { CanvasPreview } from './components/CanvasPreview';
import { Timeline } from './components/Timeline';
import { Inspector } from './components/Inspector';
import { MediaAsset, SubtitleItem, ExportConfig } from './types';
import { IPCBridge } from './engine/ipc_bridge';

export const App: React.FC = () => {
  const [assets, setAssets] = useState<MediaAsset[]>([
    { id: '1', name: 'Background_Story_01.mp4', path: 'D:\\Media\\bg1.mp4', type: 'video', duration_us: 10_000_000, width: 1920, height: 1080 },
    { id: '2', name: 'Background_Story_02.mp4', path: 'D:\\Media\\bg2.mp4', type: 'video', duration_us: 10_000_000, width: 1920, height: 1080 },
  ]);

  const [voicePath, setVoicePath] = useState('D:\\Audio\\voice_narration.mp3');
  const [srtPath, setSrtPath] = useState('D:\\Subtitle\\story_lines.srt');
  const [bgmPath, setBgmPath] = useState('D:\\Audio\\bgm_epic.mp3');

  const [strategy, setStrategy] = useState<'shuffle_bag' | 'sequential' | 'random'>('shuffle_bag');
  const [sliceMode, setSliceMode] = useState<'subtitle' | 'subtitle_group' | 'interval'>('subtitle');

  const [aspectRatio, setAspectRatio] = useState<'16:9' | '9:16' | '1:1'>('16:9');
  const [playheadUs, setPlayheadUs] = useState(0);
  const [totalDurationUs, setTotalDurationUs] = useState(10_000_000);

  const [subtitles, setSubtitles] = useState<SubtitleItem[]>([
    { id: 1, start_us: 0, end_us: 3_000_000, text: 'CapCut Long Story Studio PRO v2.0' },
    { id: 2, start_us: 3_000_000, end_us: 7_000_000, text: 'Kiến trúc mới Tauri + Rust Backend siêu nhẹ và mượt mà' },
    { id: 3, start_us: 7_000_000, end_us: 10_000_000, text: 'Xem trước Keyframe & Transition 60fps trực quan' },
  ]);

  const [exportConfig, setExportConfig] = useState<ExportConfig>({
    projectName: 'Long_Story_Draft_01',
    draftRoot: 'C:\\Users\\hieuk\\AppData\\Local\\CapCut\\User Data\\Projects\\com.lveditor.draft',
    aspectRatio: '16:9',
    strategy: 'shuffle_bag',
    sliceMode: 'subtitle',
    isCompact: true,
  });

  const [isExporting, setIsExporting] = useState(false);
  const [exportResult, setExportResult] = useState<{ success: boolean; path: string; timeMs: number } | null>(null);

  // Sync export config ratio
  useEffect(() => {
    setExportConfig((prev) => ({ ...prev, aspectRatio }));
  }, [aspectRatio]);

  const handleAddAssets = async (files: FileList) => {
    const newAssets: MediaAsset[] = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      const probed = await IPCBridge.probeMediaFile(f.name);
      newAssets.push({
        id: uuidv4(),
        name: f.name,
        path: f.name,
        type: f.type.startsWith('image/') ? 'image' : 'video',
        duration_us: probed.duration_us,
        width: probed.width,
        height: probed.height,
      });
    }
    setAssets((prev) => [...prev, ...newAssets]);
  };

  const handleExport = async () => {
    setIsExporting(true);
    setExportResult(null);

    const mediaPaths = assets.map((a) => a.path);
    const result = await IPCBridge.exportDraft(exportConfig, mediaPaths, subtitles);

    setIsExporting(false);
    setExportResult({
      success: result.success,
      path: result.draft_folder_path,
      timeMs: result.write_time_ms,
    });
  };

  return (
    <div className="studio-grid">
      {/* Studio Top Header Bar */}
      <header className="studio-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--accent-cyan)' }} />
          <span style={{ fontSize: '15px', fontWeight: 700, background: 'var(--accent-gradient)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            Vortex CapCut Studio PRO v2.0
          </span>
          <span style={{ fontSize: '10px', padding: '2px 6px', background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-subtle)', borderRadius: '4px', color: 'var(--text-muted)' }}>
            Tauri v2 + Rust Core Engine
          </span>
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
          Memory Budget: <span style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>~20.6 MB Peak RAM</span>
        </div>
      </header>

      {/* Column 1: Raw Assets & Settings (25%) */}
      <AssetPool
        assets={assets}
        onAddAssets={handleAddAssets}
        voicePath={voicePath}
        setVoicePath={setVoicePath}
        srtPath={srtPath}
        setSrtPath={setSrtPath}
        bgmPath={bgmPath}
        setBgmPath={setBgmPath}
        strategy={strategy}
        setStrategy={setStrategy}
        sliceMode={sliceMode}
        setSliceMode={setSliceMode}
      />

      {/* Column 2: Center Studio Area (50%) */}
      <div className="studio-center">
        {/* Top: WebGL Live Canvas Preview */}
        <CanvasPreview
          aspectRatio={aspectRatio}
          setAspectRatio={setAspectRatio}
          playheadUs={playheadUs}
          setPlayheadUs={setPlayheadUs}
          totalDurationUs={totalDurationUs}
        />

        {/* Bottom: Interactive Multi-Track Timeline */}
        <Timeline
          subtitles={subtitles}
          assets={assets}
          playheadUs={playheadUs}
          setPlayheadUs={setPlayheadUs}
          totalDurationUs={totalDurationUs}
        />
      </div>

      {/* Column 3: Keyframe Presets, Inspector & Export (25%) */}
      <Inspector
        exportConfig={exportConfig}
        setExportConfig={setExportConfig}
        onExport={handleExport}
        isExporting={isExporting}
        exportResult={exportResult}
      />
    </div>
  );
};

function uuidv4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0,
      v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}
