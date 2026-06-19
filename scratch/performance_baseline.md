# Performance Benchmark Report

## Configuration
- Warm-ups: 1
- Measured iterations: 5
- Mock media: 600 videos, 1 voice file
- Timeline: 5 hours, 3600 segments

## Repeated Measurements
| Phase | Median | Min | Max |
| :--- | ---: | ---: | ---: |
| Discovery | 0.054437s | 0.051660s | 0.057135s |
| Mock scan/probe | 0.441133s | 0.411974s | 0.461341s |
| Timeline planning | 1.294102s | 1.274550s | 1.331602s |
| Draft creation, cached | 3.846659s | 3.736676s | 3.884536s |
| Draft creation, uncached | 4.209577s | 4.036631s | 4.803974s |
| Pretty serialization | 0.904566s | 0.856064s | 0.976512s |
| Compact serialization | 0.775874s | 0.716998s | 0.813325s |

## Probe Calls
- Mock scan: 600
- First cached draft: 1
- Uncached draft: 601 calls across 601 unique paths
- Real ffprobe: SKIPPED: set CAPCUT_BENCHMARK_MEDIA_DIR to a folder with valid media

## Serialization
- Pretty size: 9.42 MB
- Compact size: 3.76 MB (-60.1%)
- Pretty median peak RAM: 28.03 MB
- Compact median peak RAM: 7.52 MB (-73.2%)

Mock timings validate Python call paths only. They do not measure real ffprobe CPU usage.
