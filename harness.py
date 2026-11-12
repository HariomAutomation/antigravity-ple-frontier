# Copyright 2026 Antigravity
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Antigravity PE Frontier Harness entrypoint shim.

Forwards execution to serve.py to satisfy both serve.py and harness.py
conventions in automated evaluation checks.
"""

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    serve_path = Path(__file__).resolve().parent / "serve.py"
    runpy.run_path(str(serve_path), run_name="__main__")

