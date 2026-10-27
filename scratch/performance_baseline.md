# Performance Benchmark Report

## Configuration
- Warm-ups: 1
- Measured iterations: 5
- Mock media: 600 videos, 1 voice file
- Timeline: 5 hours, 3600 segments

## Repeated Measurements
| Phase | Median | Min | Max |
| :--- | ---: | ---: | ---: |
| Discovery | 0.002484s | 0.002302s | 0.002587s |
| Mock scan/probe | 0.358184s | 0.354058s | 0.366790s |
| Timeline planning | 1.279436s | 1.273156s | 1.298759s |
| Draft creation, cached | 0.935453s | 0.926437s | 0.971798s |
| Draft creation, uncached | 1.168135s | 1.141562s | 1.224446s |
| Pretty serialization | 0.779360s | 0.764498s | 0.809840s |
| Compact serialization | 0.654877s | 0.639672s | 0.666058s |

## Probe Calls
- Mock scan: 600
- First cached draft: 1
- Uncached draft: 601 calls across 601 unique paths
- Real ffprobe: SKIPPED: set CAPCUT_BENCHMARK_MEDIA_DIR to a folder with valid media

## Serialization
- Pretty size: 9.41 MB
- Compact size: 3.74 MB (-60.2%)
- Pretty median peak RAM: 27.99 MB
- Compact median peak RAM: 7.49 MB (-73.2%)

Mock timings validate Python call paths only. They do not measure real ffprobe CPU usage.
