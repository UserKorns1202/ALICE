# ALICE Remote Access with Voice Commands

## 🎯 Overview
Control ALICE from your phone using voice commands over a secure Tailscale connection. Say "Hey Alice" or "Hey Virgil" and give commands just like you would locally.

## 🚀 Quick Start

### 1. Prerequisites
- **Tailscale installed and running** on both your PC and phone
- **Both devices connected to the same Tailscale network**

### 2. Start the Server
```bash
cd "c:\Users\troyk\OneDrive\Desktop\ALICE"
python remote_access.py
```
You should see: `[Remote] Listening on 0.0.0.0:8765 token=...`

### 3. Access from Phone
**Current Access URL:**
```
http://100.79.99.39:8765/client?token=1430cbc8efa90cc727dea5aaa81ced31
```

1. **Open the URL above** in your mobile browser
2. **Tap "🎙️ Microphone Permission"** and allow access when prompted
3. **Tap "🎤 Start Voice"** to begin listening
4. **Say your wake word + command**

## 🎙️ Voice Commands

### Wake Words
- "Hey Alice"
- "Hey Virgil" / "Hey Vergil"
- "Ok Alice"
- "Ok Virgil" / "Ok Vergil"
- "Alice"
- "Virgil" / "Vergil"

### Shutdown Commands
Say any of these to shut down ALICE:
- "goodbye"
- "exit"
- "quit"
- "shutdown"
- "bye"
- "see you"
- "good night"

### Example Commands
```
"Hey Alice, what's the weather?"
"Hey Virgil, open Chrome"
"Hey Vergil, set a timer for 5 minutes"
"Hey Alice, goodbye"
"Goodbye Virgil"
```

### Available Commands
ALICE supports all the same commands remotely as locally:
- **Program control**: "open Chrome", "close notepad"
- **System control**: "set volume to 50", "set timer for 10 minutes"
- **Information**: "what's the weather", "check my emails"
- **Automation**: "start file organization", "run security scan"
- **Communication**: "send SMS", "check notifications"

## 🔒 Security Features

- **Tailscale VPN**: Only devices on your private network can access
- **HTTPS encryption**: All communication is encrypted
- **Token authentication**: Unique access token required
- **Local voice processing**: Speech recognition happens on your phone
- **Command validation**: All commands are validated before execution

## 📱 Mobile Interface

The remote client provides:
- **Voice recognition** with continuous listening
- **Real-time status** updates
- **Push notifications** for ALICE responses
- **Command history** and logging
- **Visual feedback** for voice status
- **Text input fallback** if voice doesn't work
- **Microphone permission helper**

## 🧪 Testing

### Local Testing
```bash
python test_remote_access.py
```

### Mobile Testing Steps
1. **Open the access URL** in your mobile browser
2. **Tap "🎙️ Microphone Permission"** and allow access when prompted
3. **Tap "🎤 Start Voice"** to begin listening
4. **Say:** "Hey Alice, what's the weather?"
5. **Or use text input:** Type commands and tap "📤 Send"

## 🛠️ Troubleshooting

### Voice Not Working
- Ensure microphone permissions are granted
- Check that you're using a supported browser (Chrome/Safari)
- Try refreshing the page

### Can't Connect
- Verify Tailscale is running on both devices
- Check that both devices are on the same network
- Ensure the PC is accessible (firewall settings)

### Commands Not Responding
- Check that ALICE is running on your PC
- Verify the access token is correct
- Look at the client logs for error messages

## 🌐 External Access (Optional)

If you want to access ALICE from outside your Tailscale network:

```bash
python setup_tailscale_serve.py
```

This will give you a public HTTPS URL like:
```
https://desktop-t5lfomm.tail8c3cd9.ts.net/
```

**Note:** This exposes ALICE to the internet, so use with caution!

---

## Universal quick method (recommended): HTTPS tunnel + Chrome

If you want the simplest, most device-agnostic setup that will allow microphone permissions and let you "talk to KEVIN from anywhere", create an HTTPS tunnel to your local `remote_access.py` server. The quickest way on Windows is using `ngrok` (or `cloudflared` as an alternative). This makes the client a secure origin (HTTPS) so browsers will prompt for microphone access.

Why this works:
- `getUserMedia` (microphone/camera) requires a secure context (HTTPS) or `localhost`. A plain `http://100.x.x.x` Tailscale IP is not a secure origin for most mobile browsers.
- An HTTPS tunnel gives you a public `https://...` URL which will trigger the mic permission and allow the remote client to record/send audio or perform client-side speech recognition.

Steps (Windows / PowerShell)

1) Start ALICE remote server locally (port 8765 by default):

```powershell
cd 'C:\Users\troyk\OneDrive\Desktop\ALICE'
python .\remote_access.py
# Confirm the server says: Listening on 0.0.0.0:8765 token=...
```

2) Download and run `ngrok` (https://ngrok.com):

```powershell
# Start an http tunnel to port 8765 (ngrok prints the public https URL)
ngrok http 8765
```

3) Copy the HTTPS forwarding URL printed by ngrok (e.g. `https://abcd-12-34-56.ngrok.io`) and open the client URL on the remote device's browser (Chrome is recommended):

```
https://abcd-12-34-56.ngrok.io/client?token=YOUR_TOKEN_HERE
```

4) On the remote device (phone/tablet/laptop):
- Open the HTTPS link in Chrome (do NOT use the Google App in-app browser; if the Google app opens links by default, copy the URL and paste it into Chrome).
- When the page requests microphone permission, Accept (Allow). If you previously denied permissions, go to Chrome → Settings → Site settings → Microphone and remove any deny entries for that site, then reload.
- Tap 🎤 Start Voice and speak your wake word + command. The client will perform local recognition or stream audio back depending on your setup.

Security notes for ngrok:
- The ngrok URL is public. Treat the URL and the `token` query parameter as secrets. Stop the ngrok process when not in use.
- You can add HTTP Basic auth with ngrok (or enable ngrok authenticated tunnels) to limit access. Alternatively add server-side checks inside `remote_access.py` to validate tokens.

---

## Alternative: cloudflared (Cloudflare Tunnel)

If you prefer Cloudflare's tunnel instead of ngrok, `cloudflared` provides a similar HTTPS endpoint.

1) Install cloudflared (https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation)
2) Run the tunnel to your local server:

```powershell
cloudflared tunnel --url http://localhost:8765
```

3) `cloudflared` will print a public `https://...trycloudflare.com` URL. Open the client URL on the remote device like in the ngrok example and accept microphone permissions in Chrome.

Security note: same caveats as ngrok — protect the URL and token.

---

## Preferred (if available): Tailscale Funnel / Serve (stay inside Tailnet)

If your Tailscale account and admin console support Funnel/Serve you can create an HTTPS endpoint without third-party tunnels. This gives you a `https://<your-node>.tailscale.net` URL that is TLS-protected by Tailscale and usually works well for getUserMedia permissions.

High level:
- In the Tailscale Admin Console, enable Funnel/Serve for the machine running ALICE and configure it to forward port 8765.
- You will get an `https://...tailscale.net` URL. Open that URL in Chrome on the remote device and include the `?token=...` query param.

Notes:
- Tailscale Funnel is ideal because TLS is managed by Tailscale and you do not need to expose the machine via third-party public tunnels.
- Funnel/Serve may require a paid plan or admin enablement.

---

## How the remote client interacts with KEVIN (what you want)

- The browser client sends your spoken text or typed text to the ALICE server (`/voice-command` or similar endpoints). ALICE forwards the text to KEVIN (the LLM) and returns the assistant reply.
- With the HTTPS tunnel in place, the browser will allow microphone capture (getUserMedia) and either perform client-side speech-to-text (Web Speech API) or stream audio to ALICE for server-side ASR depending on how your client is configured.
- From the user's perspective: open the HTTPS URL in Chrome, allow the mic, say "Hey Alice..." and ALICE/KEVIN will respond and speak back through the web UI or remote audio generator.

---

## Quick checklist for the remote device (one-liner)

1. Open `https://<ngrok|cloudflared|funnel-url>/client?token=...` in Chrome.
2. Allow Microphone when prompted.
3. Tap 🎤 Start Voice, say your wake word and command, or type a command and send.

---

## 🔧 Advanced Configuration

### Custom Wake Words
Edit `wakeWords` array in the client JavaScript to add custom wake words.

### Port Configuration
The server runs on port 8765 by default. Change in `remote_access.py` if needed.

### HTTPS Setup
For production use, consider setting up proper HTTPS certificates for the Tailscale funnel or a reverse proxy (Caddy/nginx) if you host under a custom domain.

## 📋 API Endpoints

- `GET /client?token=xxx` - Main client interface
- `POST /voice-command` - Send voice commands
- `GET /events` - Real-time event stream
- `POST /subscribe` - Push notification subscription

---

**🎉 You're all set!** Say "Hey Alice" to your phone and start controlling your PC hands-free!
<parameter name="filePath">c:\Users\troyk\OneDrive\Desktop\ALICE\REMOTE_ACCESS_README.md