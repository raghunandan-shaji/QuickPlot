class QuickPlotError(Exception):
    """Base exception safe to present to an application user."""


class ProviderUnavailableError(QuickPlotError):
    pass


class ProviderAuthenticationError(QuickPlotError):
    pass


class SeriesFetchError(QuickPlotError):
    pass


class SeriesResolutionError(QuickPlotError):
    pass


class FrequencyResolutionError(QuickPlotError):
    pass


class TransformError(QuickPlotError):
    pass
