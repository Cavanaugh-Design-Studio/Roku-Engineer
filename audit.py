with open('roku_engineer.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

total_lines = len(lines)
total_bytes = sum(len(l) for l in lines)

# Count tool definitions (look for "name": inside tool list)
tool_names = []
for l in lines:
    s = l.strip()
    if s.startswith('"name":') and '"description"' not in s:
        name = s.replace('"name":', '').strip().strip('",')
        if name:
            tool_names.append(name)

# Count async def functions
func_defs = [l.strip() for l in lines if l.strip().startswith('async def ') or (l.strip().startswith('def ') and not l.strip().startswith('def _'))]

# Count templates
scenegraph_count = sum(1 for l in lines if '"Scene"' in l or '"Task"' in l or '"GridView"' in l or '"DetailsView"' in l or '"MediaView"' in l or '"ErrorView"' in l or '"CustomList"' in l or '"VideoPlayer"' in l)

print(f"=== ROKU ENGINEER STATS ===")
print(f"Total lines of code : {total_lines:,}")
print(f"Total size          : {total_bytes/1024:.1f} KB")
print(f"\n=== TOOLS ({len(tool_names)}) ===")
for t in tool_names:
    print(f"  - {t}")
print(f"\n=== TOP-LEVEL FUNCTIONS ({len(func_defs)}) ===")
for f in func_defs[:30]:
    print(f"  {f[:80]}")
