# SearchGram - Quick Deployment Guide

## 🚨 READ THIS FIRST

**⚠️ THIS WILL DELETE ALL EXISTING SEARCH DATA ⚠️**

If you have production data you want to keep, backup first!

---

## ⚡ Fast Track Deployment (10 minutes)

### Step 1: Stop Everything
```bash
pkill -f "python.*searchgram"
pkill -f "searchgram-engine"
```

### Step 2: Delete Old Index
```bash
curl -X DELETE "localhost:9200/telegram"
```

### Step 3: Build & Start Go Service
```bash
cd /home/kexi/SearchGram/searchgram-engine
go build -o searchgram-engine
./searchgram-engine
```

**✅ Wait for:** `"Created index with CJK optimization"`

### Step 4: Start Client (New Terminal)
```bash
cd /home/kexi/SearchGram
python searchgram/client.py
```

**✅ Wait for:** `"Successfully connected to search service with HTTP/2"`

### Step 5: Start Bot (New Terminal)
```bash
cd /home/kexi/SearchGram
python searchgram/bot.py
```

### Step 6: Quick Test
1. Send message in Telegram: "test message"
2. In bot: `/search test`
3. **✅ Should return the message**

### Step 7: Verify New Fields
```bash
curl -X GET "localhost:9200/telegram/_search?size=1&pretty" | grep -E "(sender_type|content_type|raw_message)"
```

**✅ Should see:**
- `"sender_type": "user"`
- `"content_type": "text"`
- `"raw_message": {`

---

## ✅ Success Checklist

- [ ] Go service shows "Created index with CJK optimization"
- [ ] Client connects successfully
- [ ] Bot connects successfully
- [ ] Test message indexed
- [ ] Search returns results
- [ ] New fields present in Elasticsearch
- [ ] No errors in logs

---

## 🐛 Quick Troubleshooting

**Can't find messages:**
- Check: `curl -X GET "localhost:9200/telegram/_count"`
- Should show: `{"count": N}` where N > 0

**Build failed:**
- Check Go version: `go version` (need 1.16+)
- Try: `go mod tidy` then rebuild

**Python errors:**
- Check config: `ls config.json`
- If missing: `cp config.example.json config.json`

**Index already exists:**
- Force delete: `curl -X DELETE "localhost:9200/telegram?ignore_unavailable=true"`

---

## 📚 Full Documentation

- **Detailed Deployment:** `PRE_DEPLOYMENT_CHECKLIST.md`
- **Testing Guide:** `TESTING_GUIDE.md`
- **Code Review:** `CODE_REVIEW_SUMMARY.md`
- **Summary:** `REFACTORING_SUMMARY.md`

---

## 🆘 Emergency Rollback

If something goes very wrong:

```bash
# Stop services
pkill -f searchgram

# Delete index
curl -X DELETE "localhost:9200/telegram"

# Revert code (if using git)
git revert HEAD

# Or restore from backup
# (if you made one)
```

---

**That's it!** You're ready to deploy. Take your time, test thoroughly, and check logs for any issues.

**Good luck!** 🚀
