#!/bin/bash
# Deploy KBLI 2025 articles to balizero.com
# Strategy: fresh clone → copy new files → commit → push → cleanup
# Double-click this file from Finder to run

set -e
PROJ="$HOME/Desktop/projects/nuzantara"
TMPDIR="$HOME/Desktop/projects/_nuzantara_deploy_tmp"

echo "🚀 Deploying KBLI 2025 articles to balizero.com..."
echo ""

# Step 1: Clean any previous temp
rm -rf "$TMPDIR"

# Step 2: Fresh clone (shallow for speed)
echo "📦 Cloning fresh copy from GitHub..."
git clone --depth 1 git@github.com:Balizero1987/Teman2.git "$TMPDIR"
echo ""

# Step 3: Copy new/modified files from working copy
echo "📋 Copying new articles and images..."

# 3a: New MDX articles (8 files)
for f in art-of-strategic-patience beginners-guide-kbli-2025 bkpm-regulation-5-2025-fdi \
         kbli-2025-bali-transformation kbli-2025-gold-rush-migration kbli-klu-fiscal-control-2025 \
         oss-kbli-2025-fiktif-positif upgrading-indonesia-kbli-2025; do
    cp "$PROJ/apps/mouth/src/content/articles/business/${f}.mdx" \
       "$TMPDIR/apps/mouth/src/content/articles/business/${f}.mdx"
    echo "  ✅ ${f}.mdx"
done

# 3b: New images (8 files)
for img in strategic-patience-editorial oss-kbli-fiktif-positif kbli-gold-rush \
           kbli-klu-fiscal bkpm-fdi-regulation kbli-bali-transformation \
           upgrading-indonesia-kbli kbli-beginners-guide; do
    cp "$PROJ/apps/mouth/public/static/insights/business/${img}.jpg" \
       "$TMPDIR/apps/mouth/public/static/insights/business/${img}.jpg"
    echo "  ✅ ${img}.jpg"
done

# 3c: Modified news page
cp "$PROJ/apps/mouth/src/app/(blog)/news/page.tsx" \
   "$TMPDIR/apps/mouth/src/app/(blog)/news/page.tsx"
echo "  ✅ news/page.tsx"

# 3d: Modified lifestyle MDX (trending demoted)
cp "$PROJ/apps/mouth/src/content/articles/lifestyle/dengue-alert-2026.mdx" \
   "$TMPDIR/apps/mouth/src/content/articles/lifestyle/dengue-alert-2026.mdx"
cp "$PROJ/apps/mouth/src/content/articles/lifestyle/suwung-landfill-crisis.mdx" \
   "$TMPDIR/apps/mouth/src/content/articles/lifestyle/suwung-landfill-crisis.mdx"
echo "  ✅ dengue-alert-2026.mdx (trending: false)"
echo "  ✅ suwung-landfill-crisis.mdx (trending: false)"

echo ""
echo "📊 Staged changes:"

# Step 4: Stage, commit, push
cd "$TMPDIR"
git add apps/mouth/
git diff --cached --stat

echo ""
echo "💾 Committing..."
git commit -m "feat: add 8 KBLI 2025 business articles with images

- 8 new MDX articles in business category
- 8 cover images in static/insights/business/
- Update news page cover: Bali Transformation + Strategic Patience
- Demote dengue and suwung from trending

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

echo ""
echo "🌐 Pushing to GitHub..."
git push origin main

# Step 5: Cleanup temp clone
echo ""
echo "🧹 Cleaning up temp directory..."
cd "$HOME"
rm -rf "$TMPDIR"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "✅ DEPLOY SUCCESSFUL!"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Vercel will auto-deploy in ~60 seconds."
echo ""
echo "Check these URLs:"
echo "  → https://balizero.com/business/kbli-2025-bali-transformation"
echo "  → https://balizero.com/business/art-of-strategic-patience"
echo "  → https://balizero.com/business/oss-kbli-2025-fiktif-positif"
echo "  → https://balizero.com/business/kbli-2025-gold-rush-migration"
echo ""
read -p "Press Enter to close..."
