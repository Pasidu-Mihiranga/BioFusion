#!/usr/bin/env bash
#
# BioFusion — VPS deployment script.
#
# Runs ON the server. Idempotent: safe as both first-time setup and as the
# redeploy step invoked by the GitHub Actions workflow on every push to main.
#
#   sudo bash deploy.sh            # full deploy (code + deps + units + nginx)
#   sudo bash deploy.sh --app-only # skip nginx/systemd file installs
#
set -euo pipefail

APP_DIR="${BIOFUSION_DIR:-/var/www/biofusion}"
REPO="${BIOFUSION_REPO:-https://github.com/Pasidu-Mihiranga/BioFusion.git}"
BRANCH="${BIOFUSION_BRANCH:-main}"
DOMAIN="${BIOFUSION_DOMAIN:-brainstorm.pasidumihiranga.me}"
STREAMLIT_PORT=8502
KIOSK_PORT=8503
SERVICES=(biofusion-streamlit biofusion-kiosk)

APP_ONLY=0
[[ "${1:-}" == "--app-only" ]] && APP_ONLY=1

log() { echo -e "\n\033[1;34m==>\033[0m $*"; }

# ── 1. Sync code ─────────────────────────────────────────────────────────────
log "Syncing code to $APP_DIR ($BRANCH)"
# Worktree is owned by www-data, git runs as root — see "dubious ownership".
git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" fetch --all --quiet
    git -C "$APP_DIR" reset --hard "origin/$BRANCH" --quiet
else
    mkdir -p "$APP_DIR"
    git clone --quiet --branch "$BRANCH" "$REPO" "$APP_DIR"
fi
git -C "$APP_DIR" log --oneline -1

# ── 2. Virtualenv + dependencies ─────────────────────────────────────────────
log "Checking Python environment"
[ -d "$APP_DIR/venv" ] || python3 -m venv "$APP_DIR/venv"

# Only reinstall when a requirements file actually changed — a full torch
# install takes minutes on a 1-vCPU droplet.
DEPS_HASH=$(cat "$APP_DIR/streamlit_app/requirements.txt" "$APP_DIR/kiosk/requirements.txt" | sha256sum | cut -d' ' -f1)
HASH_FILE="$APP_DIR/.deps-hash"

if [ "$(cat "$HASH_FILE" 2>/dev/null || echo none)" != "$DEPS_HASH" ]; then
    log "Requirements changed — installing dependencies"
    # shellcheck disable=SC1091
    source "$APP_DIR/venv/bin/activate"
    pip install --upgrade pip --quiet
    # CPU-only wheels: no GPU on this droplet and the CUDA build is ~2GB
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu --quiet
    grep -viE '^(torch|torchvision)' "$APP_DIR/streamlit_app/requirements.txt"  > /tmp/biofusion-req.txt
    grep -viE '^(torch|torchvision)' "$APP_DIR/kiosk/requirements.txt"         >> /tmp/biofusion-req.txt
    pip install -r /tmp/biofusion-req.txt --quiet
    deactivate
    echo "$DEPS_HASH" > "$HASH_FILE"
else
    log "Dependencies unchanged — skipping install"
fi

# ── 3. Model weights ─────────────────────────────────────────────────────────
# *.pth is gitignored, so weights are uploaded out of band and must survive
# the `git reset --hard` above (they live outside the worktree's tracked files).
MODELS_DIR="$APP_DIR/models"
mkdir -p "$MODELS_DIR"
log "Checking model weights in $MODELS_DIR"
MISSING=0
for w in pneumonia_resnet50_best.pth pneumonia_resnet50_combined_noPhone.pth; do
    if [ -f "$MODELS_DIR/$w" ]; then
        echo "  present  $w ($(du -h "$MODELS_DIR/$w" | cut -f1))"
    else
        echo "  MISSING  $w — that capture path falls back to DEMO MODE (ImageNet weights)"
        MISSING=1
    fi
done
[ "$MISSING" -eq 0 ] || echo "  Upload with: scp <file> root@<host>:$MODELS_DIR/"

# ── 4. Runtime dirs + permissions ────────────────────────────────────────────
log "Setting permissions"
mkdir -p "$APP_DIR/kiosk/reports" "$APP_DIR/kiosk/captures" "$APP_DIR/kiosk/overlays"
chown -R www-data:www-data "$APP_DIR"

# ── 5. systemd units + nginx ─────────────────────────────────────────────────
if [ "$APP_ONLY" -eq 0 ]; then
    log "Installing systemd units"
    for svc in "${SERVICES[@]}"; do
        install -m 644 "$APP_DIR/deploy/$svc.service" "/etc/systemd/system/$svc.service"
    done
    systemctl daemon-reload
    systemctl enable --quiet "${SERVICES[@]}"

    # certbot rewrites the installed site file in place to add the 443 block.
    # Overwriting it unconditionally on every deploy would drop TLS, so only
    # reinstall when the repo's version actually changed, then let certbot
    # re-apply its config on top.
    NGINX_SRC="$APP_DIR/deploy/nginx-biofusion.conf"

    # The config references certbot's cert paths, so installing it without a
    # certificate present would make `nginx -t` fail and take the site down.
    if grep -q "listen 443" "$NGINX_SRC" && [ ! -f /etc/letsencrypt/live/"$DOMAIN"/fullchain.pem ]; then
        echo "ERROR: $NGINX_SRC expects a certificate for $DOMAIN but none exists."
        echo "Run: certbot --nginx -d $DOMAIN"
        exit 1
    fi

    NGINX_HASH=$(sha256sum "$NGINX_SRC" | cut -d' ' -f1)
    NGINX_HASH_FILE=/etc/nginx/.biofusion-conf-hash

    if [ "$(cat "$NGINX_HASH_FILE" 2>/dev/null || echo none)" != "$NGINX_HASH" ]; then
        log "Installing nginx site for $DOMAIN"
        install -m 644 "$NGINX_SRC" /etc/nginx/sites-available/biofusion
        ln -sf /etc/nginx/sites-available/biofusion /etc/nginx/sites-enabled/biofusion

        # The repo config carries the TLS block itself, so certbot only needs to
        # run if the site file somehow lacks one.
        if ! grep -q "listen 443" /etc/nginx/sites-available/biofusion; then
            log "Re-applying certbot TLS config"
            certbot --nginx -d "$DOMAIN" --non-interactive --keep-until-expiring --redirect
        fi
        nginx -t
        systemctl reload nginx
        echo "$NGINX_HASH" > "$NGINX_HASH_FILE"
    else
        log "nginx config unchanged — leaving TLS config untouched"
    fi
fi

# ── 6. Restart services ──────────────────────────────────────────────────────
log "Restarting services"
systemctl restart "${SERVICES[@]}"

# ── 7. Health check ──────────────────────────────────────────────────────────
log "Health check"
FAILED=0
for i in $(seq 1 30); do
    KIOSK_OK=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$KIOSK_PORT/" || echo 000)
    ST_OK=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$STREAMLIT_PORT/app/_stcore/health" || echo 000)
    [ "$KIOSK_OK" = "200" ] && [ "$ST_OK" = "200" ] && break
    sleep 4
done

for svc in "${SERVICES[@]}"; do
    if systemctl is-active --quiet "$svc"; then
        echo "  OK      $svc"
    else
        echo "  FAILED  $svc"
        journalctl -u "$svc" -n 30 --no-pager
        FAILED=1
    fi
done
echo "  kiosk     HTTP $KIOSK_OK  (http://127.0.0.1:$KIOSK_PORT/)"
echo "  streamlit HTTP $ST_OK  (http://127.0.0.1:$STREAMLIT_PORT/app/)"
[ "$KIOSK_OK" = "200" ] && [ "$ST_OK" = "200" ] || FAILED=1

if [ "$FAILED" -ne 0 ]; then
    echo -e "\n\033[1;31mDEPLOY FAILED\033[0m"
    exit 1
fi

log "Deploy complete — https://$DOMAIN/  (kiosk)  |  https://$DOMAIN/app  (streamlit)"
