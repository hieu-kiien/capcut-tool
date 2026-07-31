use serde::{Deserialize, Serialize};
use super::srt::SubtitleBlock;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SliceMode {
    Subtitle,
    SubtitleGroup { count: usize },
    Interval { min_dur_us: u64, max_dur_us: u64 },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AssetStrategy {
    ShuffleBag,
    Sequential,
    Random,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KeyframePoint {
    pub time_offset_us: u64,
    pub pos_x: f64,
    pub pos_y: f64,
    pub scale_x: f64,
    pub scale_y: f64,
    pub rotation: f64,
    pub alpha: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MediaSegment {
    pub id: String,
    pub media_path: String,
    pub start_us: u64,
    pub end_us: u64,
    pub duration_us: u64,
    pub source_start_us: u64,
    pub source_duration_us: u64,
    pub keyframes: Vec<KeyframePoint>,
}

pub struct TimelineMixerPlanner;

impl TimelineMixerPlanner {
    /// O(N) single-pass timeline placement planner algorithm.
    /// Calculates background video slicing, SRT subtitle alignment, and Ken Burns keyframes.
    pub fn plan_timeline(
        subtitles: &[SubtitleBlock],
        media_pool: &[String],
        strategy: AssetStrategy,
        slice_mode: SliceMode,
    ) -> Vec<MediaSegment> {
        if media_pool.is_empty() || subtitles.is_empty() {
            return Vec::new();
        }

        let mut segments = Vec::with_capacity(subtitles.len());
        let mut pool_idx = 0;

        match slice_mode {
            SliceMode::Subtitle => {
                for sub in subtitles {
                    let media_path = &media_pool[pool_idx % media_pool.len()];
                    pool_idx += 1;

                    let dur_us = sub.end_us.saturating_sub(sub.start_us);
                    let kfs = Self::generate_ken_burns_keyframes(dur_us);

                    segments.push(MediaSegment {
                        id: uuid::Uuid::new_v4().to_string(),
                        media_path: media_path.clone(),
                        start_us: sub.start_us,
                        end_us: sub.end_us,
                        duration_us: dur_us,
                        source_start_us: 0,
                        source_duration_us: dur_us,
                        keyframes: kfs,
                    });
                }
            }
            SliceMode::SubtitleGroup { count } => {
                let chunk_size = count.max(1);
                for chunk in subtitles.chunks(chunk_size) {
                    let first_sub = &chunk[0];
                    let last_sub = chunk.last().unwrap();

                    let media_path = &media_pool[pool_idx % media_pool.len()];
                    pool_idx += 1;

                    let dur_us = last_sub.end_us.saturating_sub(first_sub.start_us);
                    let kfs = Self::generate_ken_burns_keyframes(dur_us);

                    segments.push(MediaSegment {
                        id: uuid::Uuid::new_v4().to_string(),
                        media_path: media_path.clone(),
                        start_us: first_sub.start_us,
                        end_us: last_sub.end_us,
                        duration_us: dur_us,
                        source_start_us: 0,
                        source_duration_us: dur_us,
                        keyframes: kfs,
                    });
                }
            }
            SliceMode::Interval { min_dur_us, .. } => {
                let mut current_us = 0u64;
                let total_us = subtitles.last().map(|s| s.end_us).unwrap_or(0);

                while current_us < total_us {
                    let media_path = &media_pool[pool_idx % media_pool.len()];
                    pool_idx += 1;

                    let step_us = min_dur_us.max(3_000_000);
                    let end_us = (current_us + step_us).min(total_us);
                    let dur_us = end_us.saturating_sub(current_us);
                    let kfs = Self::generate_ken_burns_keyframes(dur_us);

                    segments.push(MediaSegment {
                        id: uuid::Uuid::new_v4().to_string(),
                        media_path: media_path.clone(),
                        start_us: current_us,
                        end_us,
                        duration_us: dur_us,
                        source_start_us: 0,
                        source_duration_us: dur_us,
                        keyframes: kfs,
                    });

                    current_us = end_us;
                }
            }
        }

        segments
    }

    /// Generates normalized Ken Burns motion keyframes (Start: 1.0 scale, End: 1.15 scale zoom in)
    fn generate_ken_burns_keyframes(dur_us: u64) -> Vec<KeyframePoint> {
        vec![
            KeyframePoint {
                time_offset_us: 0,
                pos_x: 0.0,
                pos_y: 0.0,
                scale_x: 1.0,
                scale_y: 1.0,
                rotation: 0.0,
                alpha: 1.0,
            },
            KeyframePoint {
                time_offset_us: dur_us,
                pos_x: 0.0,
                pos_y: 0.0,
                scale_x: 1.15,
                scale_y: 1.15,
                rotation: 0.0,
                alpha: 1.0,
            },
        ]
    }
}
