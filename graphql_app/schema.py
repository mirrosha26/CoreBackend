import strawberry
from strawberry_django.optimizer import DjangoOptimizerExtension

from .mutations import Mutation
from .queries import Query

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[
        DjangoOptimizerExtension(
            prefetch_custom_queryset=True,
        ),
    ]
) 