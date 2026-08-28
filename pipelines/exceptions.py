class PipelineError(Exception):
    """Raised by pipelines.analyses logic modules; management commands convert this to CommandError."""
