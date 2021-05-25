import graphene


class Query(graphene.ObjectType):
    hello = graphene.String(default_value="World")
