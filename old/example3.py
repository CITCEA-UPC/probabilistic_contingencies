# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import time
from GridCalEngine.api import *


circuit_ = FileOpen('../grids/IEEE 14-2.gridcal').open()


iterator = ReliabilityIterable(grid=circuit_,
                               forced_mttf=0.1,
                               forced_mttr=1.0)

for state, pf_res in iterator:

    if sum(state) < len(state):
        print(state, "\n", np.abs(pf_res.voltage))
        time.sleep(0.1)
