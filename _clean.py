"""Remove all 2tank code from coreV5_indirect_parallel.py and fix indentation."""
with open('coreV5_indirect_parallel.py', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

# Remove all lines containing 2tank-related words
tank_kw = ['cold_source', 'hot_source', 'cold_sink', 'hot_sink',
            'conn_hot', 'conn_cold', 'ColdSource', 'HotSource',
            'ColdSink', 'HotSink', '2tank', '2tank_direct']

new_lines = []
removed = 0
for line in lines:
    skip = False
    for kw in tank_kw:
        if kw in line:
            skip = True
            break
    if skip:
        removed += 1
        continue
    new_lines.append(line)

content = '\n'.join(new_lines)
with open('coreV5_indirect_parallel.py', 'w', encoding='utf-8') as f:
    f.write(content)
print(f'Removed {removed} lines')
print(f'Remaining: {len(new_lines)} lines')
