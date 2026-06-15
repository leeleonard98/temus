"""Factory Boy factories for test data.

Empty for now — add factories as models are introduced. Pattern:

    import factory
    from app.db.models.widget import Widget

    class WidgetFactory(factory.Factory):
        class Meta:
            model = Widget

        name = factory.Sequence(lambda n: f"widget-{n}")
"""
import factory  # noqa: F401  -- ensure dep is wired and importable
