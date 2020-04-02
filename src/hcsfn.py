import json
import random
import beeline
import logging
import time
import sys
import os
import libhoney
import uuid
from datetime import datetime

logging.getLogger().setLevel(logging.DEBUG)

SERVICE_NAME = "reference-honeycomb-traced-stepfunction"
DATASET = SERVICE_NAME
WRITEKEY = os.getenv("honeycomb_api_key")


def close_final_trace(
    trace_id, span_id, parent_context_data, start_time=None,
):

    logging.info(f"Closing Overall Trace, ID={trace_id} SPAN={span_id}")
    logging.info(f"Step Function Started: {start_time.isoformat()}")

    hc = libhoney.Client(writekey=WRITEKEY, dataset=DATASET, max_concurrent_batches=1)

    ev = hc.new_event()
    ev.add_field("service_name", SERVICE_NAME)
    ev.add_field("trace.trace_id", trace_id)
    ev.add_field("trace.span_id", span_id)
    ev.add_field("name", SERVICE_NAME)
    ev.created_at = start_time
    end_time = datetime.utcnow()
    ev.add_field("end_time", end_time.isoformat())
    ev.add(parent_context_data)
    ev.add_field("duration_ms", (end_time - start_time).total_seconds() * 1000.0)

    ev.send()


def start_trace():
    logging.info(f"Starting Trace")
    return beeline.start_trace(context={"name": "reference-honeycomb-traced-stepfunction",})


def random_sleep():
    logging.info("Generating a span")
    span = beeline.start_span(context={"name": "do_assorted_data_processing"})
    time.sleep(random.randint(1, 10))
    beeline.finish_span(span)


def init_beeline():
    logging.info("Initializing Honeycomb/Beeline")
    beeline.init(
        writekey=WRITEKEY,
        dataset=DATASET,
        service_name="reference-honeycomb-traced-stepfunction",
        debug=False,
    )


def lambda_handler(event, context):

    trace_context = None
    input = None
    parent_trace = None
    output = {}

    logging.debug(f"event: {json.dumps(event)}")
    init_beeline()

    # Attempt to get trace_context(s) from the input
    input = event.get("Input", None)
    if input:
        trace_context = input.get("trace_context", None)

    # Start trace if it isn't already, otherwise resume
    if trace_context:
        trace_id, parent_id, context = beeline.trace.unmarshal_trace_context(trace_context)
        logging.info(f"Resuming trace: {trace_id}")
        trace = beeline.start_trace(trace_id=trace_id, parent_span_id=parent_id, context=context)
        # add a field to test context propogation
        beeline.add_trace_field(event.get("Path", "UnknownPath").lower(), uuid.uuid4())
        beeline.add_context({"name": event.get("Path", "Missing Path Information")})
        beeline.add_context({"function_name": event.get("Path", "Missing Path Information")})

        random_sleep()
        beeline.finish_span(trace)
    else:
        trace = start_trace()
        beeline.add_trace_field("c3po", "r2d2")
        logging.info(f"Starting Trace")
        with beeline.tracer(name=event.get("Path", "Missing Path Information")):
            random_sleep()
        trace_context = beeline.get_beeline().tracer_impl.marshal_trace_context()

    # If final step close the parent trace
    if event.get("Path") == "Step4":
        # 2019-03-26T20:14:13.192Z
        parent_trace_id, parent_parent_id, parent_context_data = beeline.trace.unmarshal_trace_context(
            trace_context
        )
        start_time = datetime.strptime(event.get("start_time"), "%Y-%m-%dT%H:%M:%S.%fZ")
        close_final_trace(parent_trace_id, parent_parent_id, parent_context_data, start_time)

    # Close only (send pending)
    beeline.close()

    # Return the trace_context to the SFN
    output["trace_context"] = trace_context
    return output
