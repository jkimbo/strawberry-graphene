from typing import Type, Optional, Sequence, List, Union, Any
from decimal import Decimal

import strawberry
from strawberry.extensions import Extension
from strawberry.middleware import DirectivesMiddleware, Middleware
from strawberry.types.types import TypeDefinition
from strawberry.union import StrawberryUnion
from strawberry.custom_scalar import ScalarDefinition
from strawberry.enum import EnumDefinition

import graphene
from graphene.types.schema import TypeMap as BaseGrapheneTypeMap

from graphql import (
    ExecutionContext as GraphQLExecutionContext,
    GraphQLSchema,
    validate_schema,
    GraphQLObjectType,
    GraphQLType,
)
from graphql.type.directives import specified_directives


class GraphQLCoreConverter(strawberry.schema.schema_converter.GraphQLCoreConverter):
    def __init__(self):
        self.type_map: GrapheneTypeMap = GrapheneTypeMap(self)

    def add_graphene_type(self, type_: Any) -> GraphQLObjectType:
        return self.type_map.add_type(type_)

    def from_object_type(self, object_type: Type) -> GraphQLObjectType:
        # Check if it's a Graphene type
        if issubclass(object_type, graphene.ObjectType):
            return self.add_graphene_type(object_type)

        return super().from_object_type(object_type)

    def get_graphql_type(self, type_: Any) -> GraphQLType:
        try:
            return super().get_graphql_type(type_)
        except TypeError:
            return self.add_graphene_type(type_)


class GrapheneTypeMap(BaseGrapheneTypeMap):
    def __init__(self, strawberry_convertor, *args, **kwargs):
        self.strawberry_convertor = strawberry_convertor
        super().__init__(*args, **kwargs)

    def add_type(self, graphene_type):
        if hasattr(graphene_type, "_type_definition") or hasattr(
            graphene_type, "_enum_definition"
        ):
            return self.strawberry_convertor.get_graphql_type(graphene_type)

        # Special case decimal
        if isinstance(graphene_type, type) and issubclass(
            graphene_type, graphene.Decimal
        ):
            return self.strawberry_convertor.from_scalar(Decimal)

        return super().add_type(graphene_type)


class Schema(strawberry.Schema):
    def __init__(
        self,
        # TODO: can we make sure we only allow to pass something that has been decorated?
        query: Type,
        mutation: Optional[Type] = None,
        subscription: Optional[Type] = None,
        directives=(),
        types=(),
        extensions: Sequence[Type[Extension]] = (),
        execution_context_class: Optional[Type[GraphQLExecutionContext]] = None,
    ):
        self.extensions = extensions
        self.execution_context_class = execution_context_class
        self.schema_converter = GraphQLCoreConverter()

        query_type = self.schema_converter.from_object_type(query)
        mutation_type = (
            self.schema_converter.from_object_type(mutation) if mutation else None
        )
        subscription_type = (
            self.schema_converter.from_object_type(subscription)
            if subscription
            else None
        )

        self.middleware: List[Middleware] = [DirectivesMiddleware(directives)]

        directives = [
            self.schema_converter.from_directive(directive.directive_definition)
            for directive in directives
        ]

        self._schema = GraphQLSchema(
            query=query_type,
            mutation=mutation_type,
            subscription=subscription_type if subscription else None,
            directives=specified_directives + directives,
            types=list(map(self.schema_converter.from_object_type, types)),
        )

        # Validate schema early because we want developers to know about
        # possible issues as soon as possible
        errors = validate_schema(self._schema)
        if errors:
            formatted_errors = "\n\n".join(f"❌ {error.message}" for error in errors)
            raise ValueError(f"Invalid Schema. Errors:\n\n{formatted_errors}")

        self.query = self.schema_converter.type_map[query_type.name]

    def get_type_by_name(
        self, name: str
    ) -> Optional[
        Union[TypeDefinition, ScalarDefinition, EnumDefinition, StrawberryUnion]
    ]:
        if name in self.schema_converter.type_map:
            return getattr(self.schema_converter.type_map[name], "definition", None)

        return None
