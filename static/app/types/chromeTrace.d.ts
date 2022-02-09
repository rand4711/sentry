// https://docs.google.com/document/d/1CvAClvFfyA5R-PhYUmn5OOQtYMH4h6I0nSsKchNAySU/preview

namespace ChromeTrace {
  interface ObjectFormat {
    traceEvents: ReadonlyArray<Event>;
    displayTimeUnit: 'ms' | 'ns';
    /**
     *  Linux ftrace data or Windows ETW trace data.
     *  This data must start with # tracer: and adhere to the
     *   Linux ftrace format or adhere to Windows ETW format.
     */
    systemTraceEvents: string;
    otherData: Record<string, string>;
    powerTraceAsString: string;
    /**
     * string that specifies which trace data comes from tracing controller.
     * Its value should be the key for that specific trace data. For example,
     * {..., "controllerTraceDataKey": "traceEvents"} means the data for traceEvents
     * comes from the tracing controller. This is mainly for the purpose of clock synchronization.
     */
    controllerTraceDataKey?: string;
    stackFrames: ReadonlyArray<any>;
    samples: ReadonlyArray<any>;
  }

  type ArrayFormat = ReadonlyArray<Event>;
  type DurationEvent = 'B' | 'E';
  type CompleteEvent = 'X';
  type InstantEvent = 'i';
  type DeprecatedInstantEvent = 'I';

  type CounterEvent = 'C';
  // b = nestable start, n = nestable instant, e = nestable end
  type AsyncEvent = 'b' | 'n' | 'e';
  // S = start, T = step into, p = step past, F = end
  type DeprecatedAsyncEvent = 'S' | 'T' | 'p' | 'F';
  // s = start, t = step, f = end
  type FlowEvent = 's' | 't' | 'f';
  type SampleEvent = 'P';
  // N = created, O = snapshot, D = destroyed
  type ObjectEvent = 'N' | 'O' | 'D';
  type MetadataEvent = 'M';
  // V = global, v = process
  type MemoryDumpEvent = 'V' | 'v';
  type MarkEvent = 'R';
  type ClockSyncEvent = 'c';
  type ContextEvents = '(,)';

  interface Event {
    name: string;
    cat: string;
    ph:
      | DurationEvent
      | CompleteEvent
      | InstantEvent
      | DeprecatedInstantEvent
      | CounterEvent
      | AsyncEvent
      | DeprecatedAsyncEvent
      | FlowEvent
      | SampleEvent
      | ObjectEvent
      | MetadataEvent
      | MemoryDumpEvent
      | MarkEvent
      | ClockSyncEvent
      | ContextEvents;
    ts: number;
    // Thread clock timestamp
    tts?: number;
    pid: number;
    tid: number;
    cname?: string;
    args: Record<string, any | Record<string, any>>;
  }

  type ProfileType = ArrayFormat | ObjectFormat;
}
