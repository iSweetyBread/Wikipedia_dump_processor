import os
import pickle

from plugin_registry import PLUGIN_REGISTRY

def dump_registered_artifacts(worker_id, state, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    serialized_files = {}

    for (state_key, artifact) in PLUGIN_REGISTRY.items():
        if state_key not in state:
            continue

        filename = (artifact.filename_template.format(worker_id=worker_id))
        path = os.path.join(output_dir, filename)

        if state_key == "edges":
            with open(path, "w", encoding="utf-8") as f:
                for src, dst in state["edges"]:
                    f.write(f"{src}\t{dst}\n")
        else:
            with open(path, "wb") as f:
                pickle.dump(state[state_key], f)

        serialized_files[state_key] = path

    return serialized_files