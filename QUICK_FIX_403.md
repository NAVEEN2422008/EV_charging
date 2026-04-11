# 🚨 403 FORBIDDEN ERROR - QUICK FIX GUIDE

**Problem**: Your Hugging Face Space returns 403 Forbidden  
**Solution**: 3 simple fixes below

---

## ⚡ QUICK FIX (3 MINUTES)

### Fix 1: Make Space PUBLIC (CRITICAL)
1. Go to your Space: `https://huggingface.co/spaces/YOUR_USER/YOUR_SPACE`
2. Click **Settings** (gear icon, top right)
3. Find **"Space Visibility"**
4. Change from **Private** to **Public**
5. Click **Save**
6. Wait 30 seconds

### Fix 2: Add Environment Variables
1. In Space Settings → **Secrets and variables**
2. Click **New secret** and add:

```
Name: API_KEY
Value: sk-... (your OpenAI API key)
```

```
Name: API_BASE_URL
Value: https://api.openai.com/v1
```

```
Name: HF_TOKEN
Value: hf_... (your Hugging Face token)
```

```
Name: MODEL_NAME
Value: gpt-4o-mini
```

### Fix 3: Trigger Rebuild
1. Go back to Space page
2. Wait for rebuild to complete (watch "Logs" tab)
3. Watch for green **"Running"** indicator

---

## ✅ VERIFY IT WORKS

```bash
# Test access (should return 200, not 403)
curl -I https://huggingface.co/spaces/YOUR_USER/YOUR_SPACE

# Visit in browser:
https://huggingface.co/spaces/YOUR_USER/YOUR_SPACE
# Should load the dashboard
```

---

## 🔍 IF IT STILL DOESN'T WORK

**Check the Logs**:
1. Go to your Space page
2. Click **"Logs"** tab  
3. Look for error messages
4. Common errors:
   - `API_KEY not set` → Add to Secrets
   - `ConnectionError` → Check internet
   - `ModuleNotFoundError` → Missing Python package

**Hard Refresh Browser**:
- Windows: `Ctrl + Shift + R`
- Mac: `Cmd + Shift + R`

---

## 📝 WHAT WAS CHANGED

Your code is **already fixed**:
- ✅ Log format: `[START]` → `[STEP] step=X reward=Y` → `[END]`
- ✅ Docker: Now runs Streamlit on port 7860
- ✅ Config: 0.0.0.0 binding + CORS enabled

**You just need to**:
1. Make Space PUBLIC
2. Add 4 Secrets
3. Let Hugging Face rebuild

---

## 🚀 DONE!

Your Space should work in < 5 minutes.

