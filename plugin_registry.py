from dataclasses import dataclass

@dataclass
class PluginArtifact:
    state_key: str
    filename_template: str

PLUGIN_REGISTRY = {}

def register_artifact(state_key, filename_template):
    def decorator(func):
        PLUGIN_REGISTRY[state_key] = PluginArtifact(state_key=state_key, filename_template=filename_template)
        return func

    return decorator