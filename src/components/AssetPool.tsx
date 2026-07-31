import React, { useState } from 'react';
import { Folder, FileAudio, FileText, Music, Image as ImageIcon, Plus } from 'lucide-react';
import { MediaAsset } from '../types';

interface AssetPoolProps {
  assets: MediaAsset[];
  onAddAssets: (files: FileList) => void;
  voicePath: string;
  setVoicePath: (p: string) => void;
  srtPath: string;
  setSrtPath: (p: string) => void;
  bgmPath: string;
  setBgmPath: (p: string) => void;
  strategy: string;
  setStrategy: (s: 'shuffle_bag' | 'sequential' | 'random') => void;
  sliceMode: string;
  setSliceMode: (m: 'subtitle' | 'subtitle_group' | 'interval') => void;
}

export const AssetPool: React.FC<AssetPoolProps> = ({
  assets,
  onAddAssets,
  voicePath,
  setVoicePath,
  srtPath,
  setSrtPath,
  bgmPath,
  setBgmPath,
  strategy,
  setStrategy,
  sliceMode,
  setSliceMode,
}) => {
  const [activeTab, setActiveTab] = useState<'media' | 'voice' | 'bgm' | 'settings'>('media');

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files) {
      onAddAssets(e.dataTransfer.files);
    }
  };

  return (
    <div className="studio-panel" style={{ height: '100%' }}>
      {/* Header Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border-subtle)', background: 'var(--bg-surface-header)' }}>
        <button
          onClick={() => setActiveTab('media')}
          style={{
            flex: 1,
            padding: '12px 8px',
            background: activeTab === 'media' ? 'var(--bg-surface)' : 'transparent',
            border: 'none',
            borderBottom: activeTab === 'media' ? '2px solid var(--accent-cyan)' : 'none',
            color: activeTab === 'media' ? 'var(--accent-cyan)' : 'var(--text-secondary)',
            fontWeight: 600,
            fontSize: '13px',
            cursor: 'pointer',
          }}
        >
          Media ({assets.length})
        </button>
        <button
          onClick={() => setActiveTab('voice')}
          style={{
            flex: 1,
            padding: '12px 8px',
            background: activeTab === 'voice' ? 'var(--bg-surface)' : 'transparent',
            border: 'none',
            borderBottom: activeTab === 'voice' ? '2px solid var(--accent-cyan)' : 'none',
            color: activeTab === 'voice' ? 'var(--accent-cyan)' : 'var(--text-secondary)',
            fontWeight: 600,
            fontSize: '13px',
            cursor: 'pointer',
          }}
        >
          Voice & SRT
        </button>
        <button
          onClick={() => setActiveTab('settings')}
          style={{
            flex: 1,
            padding: '12px 8px',
            background: activeTab === 'settings' ? 'var(--bg-surface)' : 'transparent',
            border: 'none',
            borderBottom: activeTab === 'settings' ? '2px solid var(--accent-cyan)' : 'none',
            color: activeTab === 'settings' ? 'var(--accent-cyan)' : 'var(--text-secondary)',
            fontWeight: 600,
            fontSize: '13px',
            cursor: 'pointer',
          }}
        >
          Cấu hình
        </button>
      </div>

      {/* Panel Content */}
      <div style={{ flex: 1, padding: '16px', overflowY: 'auto' }}>
        {activeTab === 'media' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <label
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              style={{
                border: '2px dashed var(--border-medium)',
                borderRadius: '8px',
                padding: '24px 16px',
                textAlign: 'center',
                cursor: 'pointer',
                background: 'var(--bg-surface-inset)',
                transition: 'border 0.2s',
              }}
            >
              <input
                type="file"
                multiple
                accept="video/*,image/*"
                onChange={(e) => e.target.files && onAddAssets(e.target.files)}
                style={{ display: 'none' }}
              />
              <Plus size={24} color="var(--accent-cyan)" style={{ margin: '0 auto 8px' }} />
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>Thêm Nguồn Media Nền</div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>Kéo thả MP4, MOV, PNG, JPG vào đây</div>
            </label>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {assets.map((item) => (
                <div
                  key={item.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '10px 12px',
                    background: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '6px',
                  }}
                >
                  <ImageIcon size={18} color="var(--track-video)" />
                  <div style={{ flex: 1, overflow: 'hidden' }}>
                    <div style={{ fontSize: '12px', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {item.name}
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                      {(item.duration_us / 1000000).toFixed(1)}s • {item.width}x{item.height}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'voice' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                Tệp Giọng Đọc Chính (Voice Narration)
              </label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  value={voicePath}
                  onChange={(e) => setVoicePath(e.target.value)}
                  placeholder="D:\Audio\voice_story.mp3"
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    background: 'var(--bg-surface-inset)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '6px',
                    color: 'var(--text-primary)',
                    fontSize: '12px',
                  }}
                />
              </div>
            </div>

            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                Tệp Phụ Đề (SRT Subtitle)
              </label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  value={srtPath}
                  onChange={(e) => setSrtPath(e.target.value)}
                  placeholder="D:\Subtitle\story.srt"
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    background: 'var(--bg-surface-inset)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '6px',
                    color: 'var(--text-primary)',
                    fontSize: '12px',
                  }}
                />
              </div>
            </div>

            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                Tệp Nhạc Nền (BGM Audio - Tùy Chọn)
              </label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  value={bgmPath}
                  onChange={(e) => setBgmPath(e.target.value)}
                  placeholder="D:\Audio\bgm_epic.mp3"
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    background: 'var(--bg-surface-inset)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '6px',
                    color: 'var(--text-primary)',
                    fontSize: '12px',
                  }}
                />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                Chế độ Trộn Media (Asset Strategy)
              </label>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value as any)}
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
                <option value="shuffle_bag">Shuffle Bag (Trộn không lặp lại)</option>
                <option value="sequential">Sequential (Lần lượt từ trên xuống)</option>
                <option value="random">Random (Ngẫu nhiên hoàn toàn)</option>
              </select>
            </div>

            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                Chế độ Cắt Phân Đoạn (Slice Mode)
              </label>
              <select
                value={sliceMode}
                onChange={(e) => setSliceMode(e.target.value as any)}
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
                <option value="subtitle">Khớp từng câu Subtitle (1 câu = 1 clip)</option>
                <option value="subtitle_group">Nhóm Subtitle (3 câu = 1 clip)</option>
                <option value="interval">Khoảng thời gian cố định (5-9s)</option>
              </select>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
