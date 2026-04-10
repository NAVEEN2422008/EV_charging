# QUICKSTART.md - Get Running in 5 Minutes

## ⚡ Installation (2 min)

```bash
# Clone or navigate to project
cd ev-charging-grid-env

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## 🚀 Run Demo (1 min)

### Option 1: Simple Inference (No LLM)
```bash
python inference.py
```

Output:
```json
{
  "success": true,
  "simulation_results": {
    "steps_executed": 300,
    "total_reward": 956.82,
    "average_reward": 3.19
  },
  "metrics": {
    "average_wait_time": 44.99,
    "solar_utilization_pct": 19.78,
    "emergency_served": 12
  }
}
```

### Option 2: Inference with LLM Analysis
```bash
export API_BASE_URL="https://api.openai.com/v1"
export API_KEY="sk-your-key-here"
python inference.py
```

The script gracefully handles missing LLM credentials.

---

## ✅ Validate Compliance (1 min)

```bash
python validate_openenv.py
```

Expected output:
```
======================================================================
  VALIDATION SUMMARY
======================================================================
  ✅ PASS     [6] All checks
  ✅ PASS     Environment Entrypoint
  ✅ PASS     Gym API Compliance
  ...
```

---

## 🎨 Launch Dashboard (1 min)

```bash
streamlit run app.py
```

Then open: **http://localhost:8501**

Tabs available:
- **Live Ops**: Real-time simulation + controls
- **Analytics**: Deep analytics + charts
- **Compare**: Policy comparison (heuristic vs random)
- **Train AI**: Launch PPO/MAPPO training

---

## 📊 Run Tests (Optional)

### All validation tests:
```bash
pytest tests/test_openenv_validation.py -v
```

### Stability tests:
```bash
pytest tests/test_stability_and_robustness.py -v
```

### All tests:
```bash
pytest tests/ -v
```

---

## 📖 Next Steps

1. **Understand the Environment**: See [USAGE_GUIDE.md](USAGE_GUIDE.md)
2. **API Reference**: See [API_REFERENCE.md](API_REFERENCE.md)
3. **Architecture Details**: See [ARCHITECTURE.md](ARCHITECTURE.md)
4. **Advanced Features**: See [ADVANCED_FEATURES.md](ADVANCED_FEATURES.md)

---

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'ev_charging_grid_env'"
```bash
pip install -e .
```

### "Port already in use" (Streamlit)
```bash
streamlit run app.py --server.port 8502
```

### Tests failing with import errors
```bash
pip install -r requirements.txt
pip install -e .
pip install pytest pytest-asyncio
```

### LLM call times out
LLM integration is optional. Environment works without it.

---

## 💡 Key Files

| File | Purpose |
|------|---------|
| `openenv.yaml` | OpenEnv specification |
| `inference.py` | Inference entry point |
| `validate_openenv.py` | Validation runner |
| `app.py` | Streamlit dashboard |
| `ev_charging_grid_env/` | Core environment |

---

## 🎯 What's Running?

When you run `python inference.py`:

1. ✅ Environment initializes with 2 charging stations
2. ✅ 300-step simulation executes
3. ✅ Heuristic agents make decisions
4. ✅ Rewards, wait times, solar usage calculated
5. ✅ Optional: LLM analyzes results
6. ✅ JSON output printed to stdout

**Total time**: ~1-2 seconds

---

## 🚀 Ready for More?

```bash
# Read usage guide
cat USAGE_GUIDE.md

# Check API reference
cat API_REFERENCE.md

# View architecture
cat ARCHITECTURE.md
```

---

**Status**: ✅ Production Ready  
**Tests**: 6/6 validation ✅, 25+ unit tests ✅  
**Documentation**: Complete with 4 guides  

**Questions?** Check the FAQ section in [USAGE_GUIDE.md](USAGE_GUIDE.md)
