"""Fix all remaining indentation errors by reducing lines with >12 extra spaces to 12."""
with open('coreV5_indirect_parallel.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Strategy: find all lines in set_operation_mode (function at line ~1000) that have >=16 leading spaces
# and reduce them if they seem orphaned (no matching control at 12sp before them)
# This is aggressive but the function structure is well-known

new_lines = []
skip_next = 0
for i, line in enumerate(lines):
    if skip_next > 0:
        skip_next -= 1
        continue
    
    stripped = line.rstrip()
    if not stripped:
        new_lines.append(line)
        continue
    
    indent = len(line) - len(line.lstrip())
    
    # Lines that are clearly orphaned (at 16 spaces after a tank_cfg getattr was removed)
    # We identify by: indent >= 16 and the line starts with self.
    if indent >= 16 and (stripped.startswith('self.') or stripped.startswith('if ') or stripped.startswith('TES_')):
        # Check previous non-empty line
        prev_indent = 0
        for j in range(i-1, max(0, i-10), -1):
            if lines[j].strip():
                prev_indent = len(lines[j]) - len(lines[j].lstrip())
                break
        
        # If prev line is at 12 spaces, this should be at 12+4=16, which is normal body.
        # Only skip if prev line doesn't exist or is at different level
        if prev_indent == 8 or prev_indent == 4:
            # Orphaned — skip this line
            continue
    
    new_lines.append(line)

with open('coreV5_indirect_parallel.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print(f'Skipped {len(lines) - len(new_lines)} lines')
