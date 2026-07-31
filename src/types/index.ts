export interface SubtitleItem {
  id: number;
  start_us: number;
  end_us: number;
  text: string;
}

export interface MediaAsset {
  id: string;
  name: string;
  path: string;
  type: 'video' | 'image' | 'audio' | 'srt';
  duration_us: number;
  width?: number;
  height?: number;
}

export interface KeyframePoint {
  time_offset_us: number;
  pos_x: number;
  pos_y: number;
  scale_x: number;
  scale_y: number;
  rotation: number;
  alpha: number;
}

export interface TimelineSegment {
  id: string;
  media_path: string;
  start_us: number;
  end_us: number;
  duration_us: number;
  keyframes: KeyframePoint[];
}

export interface ExportConfig {
  projectName: string;
  draftRoot: string;
  aspectRatio: '16:9' | '9:16' | '1:1';
  strategy: 'shuffle_bag' | 'sequential' | 'random';
  sliceMode: 'subtitle' | 'subtitle_group' | 'interval';
  isCompact: boolean;
}
