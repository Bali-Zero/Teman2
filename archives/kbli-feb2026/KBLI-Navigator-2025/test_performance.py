#!/usr/bin/env python3
"""
Performance Testing and Optimization Analysis
"""
import re
import ast
import time
import os

print("⚡ PERFORMANCE TESTS - OPTIMIZATION ANALYSIS")
print("="*70)

# Load HTML
html_file = 'app/kbli-navigator-premium.html'
with open(html_file, 'r', encoding='utf-8') as f:
    content = f.read()

file_size = os.path.getsize(html_file)

# Extract database
pattern = r'const K=(\[\s*\[[\s\S]*?\]\s*\]);'
match = re.search(pattern, content)
K = ast.literal_eval(match.group(1))

print(f"\nFile: {html_file}")
print(f"File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
print(f"Database: {len(K)} codes loaded")

print("\n" + "="*70)
print("PERFORMANCE ANALYSIS")
print("="*70)

# Test 1: File Size Analysis
print("\n[TEST 1] 📦 File Size & Load Time")
print("-" * 60)

print(f"Total file size: {file_size/1024:.1f} KB")

# Estimate components
html_length = len(content)
css_matches = re.findall(r'<style[^>]*>([\s\S]*?)</style>', content)
css_length = sum(len(m) for m in css_matches)
js_matches = re.findall(r'<script[^>]*>([\s\S]*?)</script>', content)
js_length = sum(len(m) for m in js_matches)

print(f"   HTML/Structure: ~{(html_length - css_length - js_length)/1024:.1f} KB")
print(f"   CSS: ~{css_length/1024:.1f} KB")
print(f"   JavaScript: ~{js_length/1024:.1f} KB")

# Database size
db_match = re.search(r'const K=(\[[\s\S]*?\]);', content)
if db_match:
    db_size = len(db_match.group(1))
    print(f"   Database K: ~{db_size/1024:.1f} KB ({db_size/file_size*100:.1f}%)")

# Recommendations
if file_size > 500 * 1024:
    print("\n⚠️  File is >500KB. Consider:")
    print("   • Minifying JavaScript/CSS")
    print("   • Compressing database")
    print("   • Using gzip compression on server")
else:
    print("\n✅ File size is reasonable (<500KB)")

# Test 2: Search Performance Simulation
print("\n[TEST 2] 🔍 Search Performance Simulation")
print("-" * 60)

# Simple EN2ID
EN2ID = {
    'restaurant': 'restoran makanan penyediaan',
    'agriculture': 'pertanian',
    'software': 'perangkat lunak pemrograman',
    'hotel': 'hotel'
}

STOP = ['a', 'an', 'the', 'is', 'for', 'find', 'code', 'what', 'how']

def test_search(query):
    """Simulate search function"""
    start = time.time()

    q = query.lower()
    q = re.sub(r'[^a-z0-9\s]', '', q).strip()

    words = [w for w in q.split() if len(w) > 2 and w not in STOP]

    expanded = []
    for w in words:
        expanded.append(w)
        if w in EN2ID:
            expanded.extend(EN2ID[w].split(' '))

    expanded = list(set(expanded))

    if not expanded:
        return [], time.time() - start

    # Simple scoring
    scored = []
    for entry in K:
        score = 0
        code = entry[0]
        title = entry[1].lower()
        kw = entry[7].lower() if len(entry) > 7 and entry[7] else ''

        for w in expanded:
            if w in code:
                score += 10
            if w in title:
                score += 8
            if w in kw:
                score += 6

        if score > 0:
            scored.append({'entry': entry, 'score': score})

    scored.sort(key=lambda x: x['score'], reverse=True)
    results = [s['entry'] for s in scored[:5]]

    elapsed = time.time() - start
    return results, elapsed

# Test search speed
test_queries = [
    'restaurant',
    'agriculture',
    'software development',
    'manufacturing',
    '56101',
    'e-commerce',
    'hotel accommodation',
    'food service'
]

total_time = 0
print("Search query performance:")
for query in test_queries:
    results, elapsed = test_search(query)
    total_time += elapsed
    print(f"   '{query}': {len(results)} results in {elapsed*1000:.2f}ms")

avg_time = (total_time / len(test_queries)) * 1000
print(f"\nAverage search time: {avg_time:.2f}ms")

if avg_time < 10:
    print("✅ Excellent search performance (<10ms)")
elif avg_time < 50:
    print("✅ Good search performance (<50ms)")
else:
    print("⚠️  Search could be optimized (>50ms)")

# Test 3: Database Structure Efficiency
print("\n[TEST 3] 🗃️ Database Structure Efficiency")
print("-" * 60)

# Check database format
entry_example = K[0]
print(f"Entry format: {len(entry_example)} fields")
print(f"   Fields: [code, title, sector, pma, maxForeign, risk, kondisi, keywords]")

# Calculate average entry size
avg_entry_size = sum(len(str(e)) for e in K) / len(K)
print(f"Average entry size: {avg_entry_size:.1f} chars")

# Check for optimizations
has_long_keywords = sum(1 for e in K if len(e) > 7 and e[7] and len(e[7]) > 100)
print(f"Entries with long keywords (>100 chars): {has_long_keywords}")

if avg_entry_size < 200:
    print("✅ Database structure is efficient")
else:
    print("⚠️  Database could be optimized (consider shortening keywords)")

# Test 4: Code Minification Check
print("\n[TEST 4] 🗜️ Code Minification Analysis")
print("-" * 60)

# Check for minification indicators
minification_checks = [
    ('Whitespace compression', len(re.findall(r'\n\s+', content)) < 100),
    ('Variable names shortened', 'const K=' in content),  # K instead of KBLI_DATA
    ('Comments removed', content.count('//') + content.count('/*') < 50),
]

minified_score = sum(1 for _, check in minification_checks if check)

print("Minification status:")
for desc, status in minification_checks:
    status_icon = '✅' if status else '⚠️'
    print(f"   {status_icon} {desc}")

if minified_score == len(minification_checks):
    print("\n✅ Code is well minified")
else:
    print(f"\n⚠️  Code minification: {minified_score}/{len(minification_checks)} checks passed")

# Test 5: Loading Strategy
print("\n[TEST 5] 📥 Loading Strategy Analysis")
print("-" * 60)

# Check for loading optimizations
loading_features = [
    ('Lazy loading', 'lazy' in content.lower() or 'defer' in content.lower()),
    ('Progressive rendering', 'requestAnimationFrame' in content or 'setTimeout' in content),
    ('Database preload', 'const K=' in content[:10000]),  # K defined early
]

print("Loading optimizations:")
for feature, present in loading_features:
    status = '✅' if present else '⚠️'
    print(f"   {status} {feature}: {'Yes' if present else 'No'}")

# Test 6: DOM Operations Efficiency
print("\n[TEST 6] 🎨 DOM Operations Efficiency")
print("-" * 60)

# Check for efficient DOM patterns
dom_patterns = [
    ('Document fragments', 'DocumentFragment' in content or 'createDocumentFragment' in content),
    ('Event delegation', 'addEventListener' in content),
    ('Batch updates', 'innerHTML' in content or 'textContent' in content),
]

print("DOM operation patterns:")
for pattern, found in dom_patterns:
    status = '✅' if found else '⚠️'
    print(f"   {status} {pattern}: {'Yes' if found else 'No'}")

# Test 7: Memory Usage Estimate
print("\n[TEST 7] 💾 Memory Usage Estimation")
print("-" * 60)

# Estimate memory for database
db_memory = len(str(K))
print(f"Database in memory: ~{db_memory/1024:.1f} KB")

# Estimate total JavaScript memory
js_memory_estimate = file_size * 1.5  # JS typically uses 1.5x file size in memory
print(f"Estimated JS memory: ~{js_memory_estimate/1024:.1f} KB")

total_memory = db_memory + js_memory_estimate
print(f"Total estimated memory: ~{total_memory/1024:.1f} KB")

if total_memory < 5 * 1024 * 1024:  # 5MB
    print("✅ Memory usage is reasonable (<5MB)")
else:
    print("⚠️  High memory usage (>5MB)")

# Test 8: Browser Compatibility
print("\n[TEST 8] 🌐 Browser Compatibility Check")
print("-" * 60)

# Check for modern features that might need polyfills
modern_features = [
    ('Arrow functions', '=>' in content),
    ('Template literals', '`' in content),
    ('Const/Let', 'const ' in content or 'let ' in content),
    ('Spread operator', '...' in content),
]

print("Modern JavaScript features used:")
for feature, used in modern_features:
    status = '⚠️' if used else '✅'
    note = 'Needs ES6+ support' if used else 'Compatible'
    print(f"   {status} {feature}: {note}")

# Test 9: Caching Strategy
print("\n[TEST 9] 💨 Caching Strategy")
print("-" * 60)

# Check for caching indicators
caching_features = [
    ('localStorage', 'localStorage' in content),
    ('sessionStorage', 'sessionStorage' in content),
    ('Cache API', 'caches' in content.lower()),
    ('Service Worker', 'serviceWorker' in content),
]

print("Caching mechanisms:")
for feature, present in caching_features:
    status = '✅' if present else '⚠️'
    print(f"   {status} {feature}: {'Yes' if present else 'No'}")

# Test 10: Performance Recommendations
print("\n[TEST 10] 💡 Performance Recommendations")
print("-" * 60)

recommendations = []

if file_size > 400 * 1024:
    recommendations.append("• Consider code splitting or lazy loading")

if avg_time > 20:
    recommendations.append("• Optimize search algorithm (consider indexing)")

if minified_score < len(minification_checks):
    recommendations.append("• Apply full minification to CSS/JS")

if not any(p[1] for p in caching_features):
    recommendations.append("• Implement caching (localStorage or Service Worker)")

if has_long_keywords > 50:
    recommendations.append("• Shorten keyword strings to reduce database size")

if recommendations:
    print("Recommended optimizations:")
    for rec in recommendations:
        print(f"   {rec}")
else:
    print("✅ No critical optimizations needed")

# Summary
print("\n" + "="*70)
print("📊 PERFORMANCE SUMMARY")
print("="*70)

performance_score = 0
max_score = 10

# Score each category
if file_size < 500 * 1024:
    performance_score += 1
if avg_time < 20:
    performance_score += 2
if minified_score >= 2:
    performance_score += 1
if db_memory < 200 * 1024:
    performance_score += 1
if total_memory < 5 * 1024 * 1024:
    performance_score += 1
if any(p[1] for p in caching_features):
    performance_score += 2
if any(p[1] for p in dom_patterns):
    performance_score += 1
if any(p[1] for p in loading_features):
    performance_score += 1

print(f"""
Performance Score: {performance_score}/{max_score}

✅ Strengths:
   • File size: {file_size/1024:.1f} KB
   • Search speed: {avg_time:.2f}ms average
   • Database: {len(K)} codes efficiently stored
   • Memory usage: ~{total_memory/1024:.1f} KB

{'⚠️  Areas for Improvement:' if recommendations else '🎯 Excellent Performance!'}
""")

if recommendations:
    for rec in recommendations:
        print(f"   {rec}")
else:
    print("   No critical optimizations needed!")

print("\n🎯 Overall: {'Excellent' if performance_score >= 8 else 'Good' if performance_score >= 6 else 'Needs Optimization'}")
