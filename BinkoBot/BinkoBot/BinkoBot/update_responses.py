import os
import re

modules_dir = "modules"  # adjust if yours is nested
for root, dirs, files in os.walk(modules_dir):
    for filename in files:
        if filename.endswith(".py"):
            path = os.path.join(root, filename)
            with open(path, "r", encoding="utf-8") as file:
                code = file.read()

            # Replace DM sends with public sends
            new_code = re.sub(r"await\s+ctx\.author\.send\(", "await ctx.send(", code)

            if new_code != code:
                with open(path, "w", encoding="utf-8") as file:
                    file.write(new_code)
                print(f"✔ Updated: {filename}")
