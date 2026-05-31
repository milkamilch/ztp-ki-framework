"""
Erzeugt ki/model-demo.joblib mit 80 synthetischen Normal-Samples.

Das vortrainierte Modell überspringt die Warmup-Phase beim Demo-Start,
sodass der Isolation Forest sofort aktiv ist und ML_OUTLIER-Erkennung
schon beim ersten Poll funktioniert.

Ausführen:
    python -m ki.train_demo_model
"""
from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Feature-Vektor: [mean_temp, max_temp, mean_fan, min_fan, mean_power, critical_sel_count]
# Basiert auf dem "normal"-Szenario des Mock-BMC mit etwas zufälliger Variation
RNG = np.random.default_rng(42)

N = 120

mean_temps  = RNG.normal(35.0, 2.5, N)
max_temps   = mean_temps + RNG.uniform(5.0, 12.0, N)
mean_fans   = RNG.normal(5980.0, 120.0, N)
min_fans    = mean_fans - RNG.uniform(80.0, 200.0, N)
mean_powers = RNG.normal(350.0, 20.0, N)
sel_counts  = np.zeros(N)

X = np.column_stack([mean_temps, max_temps, mean_fans, min_fans, mean_powers, sel_counts])

model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
model.fit(X)

out = Path("ki/model-demo.joblib")
joblib.dump(model, out)
logger.info("Demo-Modell gespeichert: %s  (%d Samples, contamination=0.05)", out, N)
