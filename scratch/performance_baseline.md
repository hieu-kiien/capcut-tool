# Performance Benchmark Report

## Configuration
- Warm-ups: 1
- Measured iterations: 5
- Mock media: 600 videos, 1 voice file
- Timeline: 5 hours, 3600 segments

## Repeated Measurements
| Phase | Median | Min | Max |
| :--- | ---: | ---: | ---: |
| Discovery | 0.054757s | 0.050014s | 0.063806s |
| Mock scan/probe | 0.480982s | 0.404999s | 0.507931s |
| Timeline planning | 1.328382s | 1.255618s | 1.417396s |
| Draft creation, cached | 4.021734s | 3.780976s | 4.096135s |
| Draft creation, uncached | 4.264534s | 4.176871s | 4.384845s |
| Pretty serialization | 0.939673s | 0.891530s | 1.027166s |
| Compact serialization | 0.766857s | 0.733491s | 0.805148s |

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
