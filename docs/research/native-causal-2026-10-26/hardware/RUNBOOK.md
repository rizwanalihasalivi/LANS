# Target-hardware and real-vehicle validation handoff

Status: **NOT RUN — no target controller board, vehicle, CAN device, encoder acknowledgement stream or real-time scheduler privileges is attached to this cloud environment.** This document and its checker are deliverables, not fabricated hardware results.

## Required instrumentation

Use the actual deployment CPU/OS, model/profile hashes, firmware and vehicle interface. Record current sensor acquisition, original learned-packet observation, worker request/start/end, command transmission, hardware acknowledgement and encoder sample times. All timestamps must be mapped into a calibrated monotonic nanosecond domain; retain the calibration record and uncertainty bound (at most 1 ms for this checker). A simulator step or a successful socket send is not a physical acknowledgement.

Record each 10 ms scheduled release even when late. Keep missing, rejected, stale and worker-failure ticks. Log the actually transmitted steering command and the encoder angle, not just an intermediate candidate. Never refresh a held packet's observation timestamp. The logger should remain independent of the inference process so a worker crash does not remove the evidence.

Run the five predeclared scenarios `nominal`, `delay20`, `delay100`, `cpu_stress`, `worker_crash` on the instrumented target. Keep at least 1,000 consecutive control rows per scenario; use one continuous sequence and monotonic clock, or evaluate separate complete campaigns. Preserve CPU load configuration, external fault-injection logs and observed actuator response. Physical vehicle tests require the vehicle operator and an appropriate test facility; this repository does not remotely operate the vehicle.

## CSV schema

One row per control cycle, with header:

```text
scenario,control_sequence,control_release_ns,control_deadline_ns,current_sensor_ns,packet_sequence,packet_observed_ns,request_ns,infer_start_ns,infer_end_ns,command_ns,ack_ns,encoder_ns,actuator_angle_rad,learned_weight,command_rad,lqr_rad,worker_healthy
```

Use `packet_sequence=-1` when there is no learned packet. Other packet timestamp fields are ignored in that case and learned weight must be zero. Preserve the original packet fields for held commands. Use `worker_healthy=0` after confirmed worker death. Encoder samples must increase monotonically; acknowledgement must refer to the logged command.

Metadata JSON must include:

- `trace_kind`: `target_hardware` or `real_vehicle` (simulation is rejected).
- `device_id`, `cpu`, `os`, `controller_commit`, `firmware_id`.
- `csv_sha256` of the exact CSV bytes.
- `timestamps_same_monotonic_domain: true`, `clock_uncertainty_ns`, and `clock_calibration_record`.
- `physical_acknowledgements: true`, supported by retained interface/device records.

Do not fill these fields with assumed values. Checker metadata is self-reported and must be independently verified against the actual instruments.

## Evaluate the captured evidence

```bash
python tools/controller_review/hardware_acceptance.py \
  --metadata captured-hardware.json --csv captured-hardware.csv \
  --output new-hardware-assessment.json
```

The checker is read-only and refuses to overwrite an assessment. It checks exact 10 ms deadlines using acknowledgement times plus clock uncertainty, original packet age below 50 ms when learned authority is used, bounded angles and measured encoder rate, baseline fallback, timestamp order, and minimum scenario coverage. It rejects incomplete and simulated evidence.

A passing trace is **not vehicle safety certification**. Broad tracking/failure performance and vehicle readiness require native and physical evaluation, reviewed calibration, fault coverage, and the separately frozen comparison. No automated checker can establish that self-reported physical provenance is truthful.
