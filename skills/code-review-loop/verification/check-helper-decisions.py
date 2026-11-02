#!/usr/bin/env python3
"""Check the model's decision function against every finite helper input class.

Only dispatcher_loop.decide_action is called; it performs no protocol I/O.
The temporary model adds a constant assertion containing actual Python outputs.
This catches policy/model drift without running a dispatcher or touching sessions.
"""

from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from dispatcher_loop import WORKER_STATUSES, decide_action


def boolean(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def main() -> int:
    rows = []
    for (
        closed,
        close,
        bound,
        pending,
        dispatch,
        shutdown,
        observed,
    ) in itertools.product(
        (False, True),
        (False, True),
        (False, True),
        (False, True),
        (False, True),
        (False, True),
        WORKER_STATUSES,
    ):
        info = {
            "session_status": "closed" if closed else "open",
            "close_requested": close,
            "worker_handle": "handle" if bound else None,
            "review_pending": pending,
            "dispatch_requested": dispatch,
        }
        result = decide_action(info, observed, shutdown)
        record = (
            f"[closed |-> {boolean(closed)}, close |-> {boolean(close)}, "
            f"handle |-> {int(bound)}, lock |-> {boolean(pending)}, dispatch |-> {boolean(dispatch)}]"
        )
        rows.append(
            f"    /\\ Decide({record}, {json.dumps(observed)}, "
            f"{boolean(shutdown)}) = {json.dumps(result)}"
        )
    source = (HERE / "CodeReviewLoop.tla").read_text()
    ending = (
        "============================================================================="
    )
    if source.count(ending) != 1:
        raise ValueError("expected one module terminator")
    source = source.replace(
        ending,
        "HelperDecisionParity ==\n"
        + "\n".join(rows)
        + "\nASSUME HelperDecisionParity\nParityNoNext == UNCHANGED vars\n"
        + ending,
    )
    constants = (HERE / "CodeReviewLoop.cfg").read_text().split("CONSTANTS", 1)[1]
    constants = constants.split("INVARIANTS", 1)[0]
    with tempfile.TemporaryDirectory(prefix="code-review-loop-policy-") as temporary:
        directory = Path(temporary)
        model = directory / "CodeReviewLoop.tla"
        config = directory / "parity.cfg"
        model.write_text(source)
        config.write_text(
            "INIT Init\nNEXT ParityNoNext\nCONSTANTS" + constants + "INVARIANT TypeOK\n"
        )
        env = dict(
            os.environ,
            TLC_MODEL=str(model),
            TLC_CONFIG=str(config),
            TLC_METADIR=str(directory / "states"),
        )
        result = subprocess.run(
            [str(HERE / "run-tlc.sh")],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if (
        result.returncode
        or "Model checking completed. No error has been found." not in result.stdout
    ):
        print(result.stdout, file=sys.stderr)
        return 1
    print(f"Model/helper decision parity: all {len(rows)} input classes agree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
