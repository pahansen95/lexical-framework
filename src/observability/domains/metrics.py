"""
Metrics domain for quantitative measurement and statistical aggregation.

The metrics domain provides numeric measurements that track system behavior over time.
Unlike logs that record individual events or traces that capture execution flow,
metrics aggregate data points into statistical summaries suitable for monitoring,
alerting, and performance analysis.

Mental Model:
Metrics are the vital signs of your application. Like a heartbeat monitor that shows
beats per minute rather than individual heartbeats, metrics summarize activity into
measurable quantities. They answer questions like "how many?", "how fast?", and
"how much?" by aggregating individual measurements into meaningful statistics.

Key Concepts:
- Counter: Monotonically increasing value (requests served, errors encountered)
- Gauge: Point-in-time measurement (memory usage, queue depth)
- Histogram: Distribution of values (request latencies, payload sizes)
- Labels: Dimensional data for metric segmentation (status_code, endpoint)

Design Principles:
- Minimize measurement overhead through efficient aggregation
- Support high-cardinality data with bounded memory usage
- Enable dimensional analysis through label-based filtering
- Maintain accuracy while reducing data volume

The implementation emits raw measurement events that handlers aggregate into
statistical summaries. This separation allows flexible aggregation strategies
while maintaining a consistent emission interface.
"""

from collections import defaultdict
from typing import Any, Dict, Final, List, Optional, Tuple
import time

from ..core import emit, has_handlers

# Event schema
METRIC_PREFIX: Final[str] = "metric"
METRIC_COUNTER: Final[str] = f"{METRIC_PREFIX}.counter"
METRIC_GAUGE: Final[str] = f"{METRIC_PREFIX}.gauge"
METRIC_HISTOGRAM: Final[str] = f"{METRIC_PREFIX}.histogram"

# Label validation
MAX_LABEL_KEY_LENGTH: Final[int] = 100
MAX_LABEL_VALUE_LENGTH: Final[int] = 200
MAX_LABELS_PER_METRIC: Final[int] = 10


class Counter:
    """
    Monotonically increasing counter metric.
    
    Counters track cumulative values that only increase over time,
    such as total requests processed or bytes transmitted.
    """
    
    __slots__ = ('name', 'labels', 'help')
    
    def __init__(self, name: str, help: str = '', **labels: str):
        """
        Initialize counter.
        
        Args:
            name: Metric name
            help: Human-readable description
            **labels: Static labels for this counter instance
        """
        self.name = name
        self.help = help
        self.labels = self._validate_labels(labels)
    
    def increment(self, value: int = 1, **labels: str) -> None:
        """
        Increment counter by value.
        
        Args:
            value: Amount to increment (must be positive)
            **labels: Additional dynamic labels
        """
        if not has_handlers():
            return
        
        if value < 0:
            raise ValueError("Counter can only increase")
        
        all_labels = {**self.labels, **labels}
        emit(METRIC_COUNTER,
             self.name,
             measurement=value,
             help=self.help,
             **all_labels)
    
    def _validate_labels(self, labels: Dict[str, str]) -> Dict[str, str]:
        """Validate label constraints."""
        if len(labels) > MAX_LABELS_PER_METRIC:
            raise ValueError(f"Too many labels: {len(labels)} > {MAX_LABELS_PER_METRIC}")
        
        for key, value in labels.items():
            if len(key) > MAX_LABEL_KEY_LENGTH:
                raise ValueError(f"Label key too long: {key}")
            if len(str(value)) > MAX_LABEL_VALUE_LENGTH:
                raise ValueError(f"Label value too long: {value}")
        
        return labels


class Gauge:
    """
    Point-in-time value metric.
    
    Gauges represent instantaneous measurements that can increase
    or decrease, such as temperature or active connections.
    """
    
    __slots__ = ('name', 'labels', 'help')
    
    def __init__(self, name: str, help: str = '', **labels: str):
        """
        Initialize gauge.
        
        Args:
            name: Metric name
            help: Human-readable description
            **labels: Static labels for this gauge instance
        """
        self.name = name
        self.help = help
        self.labels = self._validate_labels(labels)
    
    def set(self, value: float, **labels: str) -> None:
        """
        Set gauge to specific value.
        
        Args:
            value: Current measurement
            **labels: Additional dynamic labels
        """
        if not has_handlers():
            return
        
        all_labels = {**self.labels, **labels}
        emit(METRIC_GAUGE,
             self.name,
             measurement=value,
             help=self.help,
             **all_labels)
    
    def increment(self, value: float = 1.0, **labels: str) -> None:
        """Increment gauge (convenience method)."""
        # Note: In production, gauges should track state
        # This is simplified for the example
        if not has_handlers():
            return
        
        all_labels = {**self.labels, **labels}
        emit(METRIC_GAUGE,
             self.name,
             measurement=value,
             delta=True,
             help=self.help,
             **all_labels)
    
    def _validate_labels(self, labels: Dict[str, str]) -> Dict[str, str]:
        """Validate label constraints."""
        if len(labels) > MAX_LABELS_PER_METRIC:
            raise ValueError(f"Too many labels: {len(labels)} > {MAX_LABELS_PER_METRIC}")
        
        for key, value in labels.items():
            if len(key) > MAX_LABEL_KEY_LENGTH:
                raise ValueError(f"Label key too long: {key}")
            if len(str(value)) > MAX_LABEL_VALUE_LENGTH:
                raise ValueError(f"Label value too long: {value}")
        
        return labels


class Histogram:
    """
    Distribution of values metric.
    
    Histograms track the statistical distribution of values,
    such as request durations or response sizes.
    """
    
    __slots__ = ('name', 'labels', 'help', 'buckets')
    
    def __init__(self, name: str, help: str = '', 
                 buckets: Optional[Tuple[float, ...]] = None, **labels: str):
        """
        Initialize histogram.
        
        Args:
            name: Metric name
            help: Human-readable description
            buckets: Bucket boundaries for distribution
            **labels: Static labels for this histogram instance
        """
        self.name = name
        self.help = help
        self.labels = self._validate_labels(labels)
        # Default buckets for typical latencies in seconds
        self.buckets = buckets or (
            0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75,
            1.0, 2.5, 5.0, 7.5, 10.0
        )
    
    def observe(self, value: float, **labels: str) -> None:
        """
        Record an observation.
        
        Args:
            value: Observed measurement
            **labels: Additional dynamic labels
        """
        if not has_handlers():
            return
        
        all_labels = {**self.labels, **labels}
        emit(METRIC_HISTOGRAM,
             self.name,
             measurement=value,
             buckets=self.buckets,
             help=self.help,
             **all_labels)
    
    def _validate_labels(self, labels: Dict[str, str]) -> Dict[str, str]:
        """Validate label constraints."""
        if len(labels) > MAX_LABELS_PER_METRIC:
            raise ValueError(f"Too many labels: {len(labels)} > {MAX_LABELS_PER_METRIC}")
        
        for key, value in labels.items():
            if len(key) > MAX_LABEL_KEY_LENGTH:
                raise ValueError(f"Label key too long: {key}")
            if len(str(value)) > MAX_LABEL_VALUE_LENGTH:
                raise ValueError(f"Label value too long: {value}")
        
        return labels


def create_metrics_aggregator(
    window_seconds: int = 60,
    export_interval: int = 10
) -> Any:
    """
    Create a handler that aggregates metrics over time windows.
    
    Args:
        window_seconds: Aggregation window size
        export_interval: How often to export aggregated metrics
        
    Returns:
        Event handler that aggregates metric events
    """
    # Storage for aggregations
    counters: Dict[str, float] = defaultdict(float)
    gauges: Dict[str, float] = {}
    histograms: Dict[str, List[float]] = defaultdict(list)
    
    last_export = time.time()
    
    def metrics_handler(event: Dict[str, Any]) -> None:
        if not event['type'].startswith(METRIC_PREFIX):
            return
        
        nonlocal last_export
        
        # Extract metric identity
        name = event['value']
        labels = {k: v for k, v in event.items() 
                 if k not in ['type', 'value', 'measurement', 'timestamp_ns', 
                             'help', 'buckets', 'delta']}
        metric_id = f"{name},{','.join(f'{k}={v}' for k, v in sorted(labels.items()))}"
        
        # Aggregate based on type
        event_type = event['type']
        measurement = event.get('measurement', 0)
        
        if event_type == METRIC_COUNTER:
            counters[metric_id] += measurement
        
        elif event_type == METRIC_GAUGE:
            if event.get('delta'):
                gauges[metric_id] = gauges.get(metric_id, 0) + measurement
            else:
                gauges[metric_id] = measurement
        
        elif event_type == METRIC_HISTOGRAM:
            histograms[metric_id].append(measurement)
        
        # Export if interval elapsed
        current_time = time.time()
        if current_time - last_export >= export_interval:
            _export_metrics(counters, gauges, histograms)
            last_export = current_time
    
    def _export_metrics(counters: Dict[str, float], 
                       gauges: Dict[str, float],
                       histograms: Dict[str, List[float]]) -> None:
        """Export aggregated metrics."""
        print(f"\n=== Metrics Export at {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
        
        # Export counters
        if counters:
            print("\nCounters:")
            for metric_id, value in sorted(counters.items()):
                print(f"  {metric_id}: {value}")
        
        # Export gauges
        if gauges:
            print("\nGauges:")
            for metric_id, value in sorted(gauges.items()):
                print(f"  {metric_id}: {value}")
        
        # Export histograms (simplified - just show count, min, max, avg)
        if histograms:
            print("\nHistograms:")
            for metric_id, values in sorted(histograms.items()):
                if values:
                    count = len(values)
                    min_val = min(values)
                    max_val = max(values)
                    avg_val = sum(values) / count
                    print(f"  {metric_id}: count={count}, min={min_val:.3f}, "
                          f"max={max_val:.3f}, avg={avg_val:.3f}")
        
        # Clear histogram data after export (counters/gauges persist)
        histograms.clear()
    
    metrics_handler.__name__ = f"metrics_aggregator(window={window_seconds}s)"
    return metrics_handler


# Convenience functions
def timer() -> 'Timer':
    """Create a timer context manager for measuring durations."""
    return Timer()


class Timer:
    """Context manager for timing operations."""
    
    __slots__ = ('start_ns', 'duration_ns')
    
    def __enter__(self) -> 'Timer':
        self.start_ns = time.perf_counter_ns()
        return self
    
    def __exit__(self, *args) -> None:
        self.duration_ns = time.perf_counter_ns() - self.start_ns
    
    @property
    def duration_seconds(self) -> float:
        """Duration in seconds."""
        return self.duration_ns / 1_000_000_000


# Public exports
__all__ = [
    # Metric types
    'Counter',
    'Gauge', 
    'Histogram',
    
    # Utilities
    'timer',
    'Timer',
    
    # Handlers
    'create_metrics_aggregator',
]