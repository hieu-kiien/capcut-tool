import { SubtitleItem, ExportConfig } from '../types';

export interface MediaProbeResult {
  path: string;
  duration_us: number;
  width: number;
  height: number;
  fps: number;
  codec_name: string;
  file_size: number;
  has_audio: boolean;
  has_video: boolean;
}

export interface SrtParseResult {
  path: string;
  subtitles_count: number;
  total_duration_us: number;
  subtitles: SubtitleItem[];
}

export interface ExportResult {
  success: boolean;
  draft_folder_path: string;
  content_bytes: number;
  meta_bytes: number;
  write_time_ms: number;
}

export class IPCBridge {
  private static isTauriAvailable(): boolean {
    return typeof window !== 'undefined' && '__TAURI__' in window;
  }

  public static async probeMediaFile(path: string): Promise<MediaProbeResult> {
    if (this.isTauriAvailable()) {
      const { invoke } = await import('@tauri-apps/api/core');
      return await invoke<MediaProbeResult>('probe_media_file', { path });
    }
    // Browser fallback simulation
    return {
      path,
      duration_us: 10_000_000,
      width: 1920,
      height: 1080,
      fps: 30,
      codec_name: 'h264',
      file_size: 15_420_000,
      has_audio: true,
      has_video: true,
    };
  }

  public static async parseSrtFile(path: string): Promise<SrtParseResult> {
    if (this.isTauriAvailable()) {
      const { invoke } = await import('@tauri-apps/api/core');
      return await invoke<SrtParseResult>('parse_srt_file', { path });
    }
    // Browser fallback simulation
    const subs: SubtitleItem[] = [
      { id: 1, start_us: 0, end_us: 3_000_000, text: 'CapCut Long Story Studio PRO v2.0' },
      { id: 2, start_us: 3_000_000, end_us: 7_000_000, text: 'Hệ thống dựng video tự động bằng Tauri + Rust Backend' },
      { id: 3, start_us: 7_000_000, end_us: 10_000_000, text: 'Xem trước Keyframe & Transition 60fps mượt mà' },
    ];
    return {
      path,
      subtitles_count: subs.length,
      total_duration_us: 10_000_000,
      subtitles: subs,
    };
  }

  public static async exportDraft(config: ExportConfig, mediaPaths: string[], subtitles: SubtitleItem[]): Promise<ExportResult> {
    if (this.isTauriAvailable()) {
      const { invoke } = await import('@tauri-apps/api/core');
      return await invoke<ExportResult>('export_capcut_draft', {
        params: {
          project_name: config.projectName,
          draft_root: config.draftRoot,
          aspect_ratio: config.aspectRatio,
          is_compact: config.isCompact,
          media_segments: mediaPaths.map((p, i) => ({
            id: `seg_${i}`,
            media_path: p,
            start_us: i * 3_000_000,
            end_us: (i + 1) * 3_000_000,
            duration_us: 3_000_000,
            source_start_us: 0,
            source_duration_us: 3_000_000,
            keyframes: [
              { time_offset_us: 0, pos_x: 0, pos_y: 0, scale_x: 1.0, scale_y: 1.0, rotation: 0, alpha: 1.0 },
              { time_offset_us: 3_000_000, pos_x: 0, pos_y: 0, scale_x: 1.15, scale_y: 1.15, rotation: 0, alpha: 1.0 },
            ],
          })),
          subtitles,
        },
      });
    }
    // Browser fallback simulation
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          success: true,
          draft_folder_path: `${config.draftRoot}/${config.projectName}`,
          content_bytes: 32_450_000,
          meta_bytes: 1_200,
          write_time_ms: 38,
        });
      }, 500);
    });
  }
}
