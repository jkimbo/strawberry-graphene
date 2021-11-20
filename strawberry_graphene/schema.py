# Based on https://github.com/jkimbo/strawberry-graphene/blob/main/strawberry_graphene/schema.py
import inspect
from decimal import Decimal
from typing import Any, Dict, Optional, Sequence, Type, Union

import graphene
import strawberry
from graphene.types.base import BaseType as BaseGrapheneType
from graphene.types.schema import TypeMap as BaseGrapheneTypeMap
from graphql import (
    ExecutionContext as GraphQLExecutionContext,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLType,
    validate_schema,
)
from graphql.type.directives import specified_directives
from strawberry.custom_scalar import ScalarDefinition, ScalarWrapper
from strawberry.directive import StrawberryDirective
from strawberry.enum import EnumDefinition
from strawberry.extensions import Extension
from strawberry.schema import schema_converter
from strawberry.schema.config import StrawberryConfig
from strawberry.schema.types import ConcreteType
from strawberry.schema.types.scalar import DEFAULT_SCALAR_REGISTRY
from strawberry.types.types import TypeDefinition
from strawberry.union import StrawberryUnion


class GraphQLCoreConverter(schema_converter.GraphQLCoreConverter):
    def __init__(self, *args, **kwargs):
        self.graphene_type_map = GrapheneTypeMap(self)
        super().__init__(*args, **kwargs)

    def add_graphene_type(self, type_: Any) -> GraphQLObjectType:
        return self.graphene_type_map.add_type(type_)

    def from_object_type(self, object_type: Type) -> GraphQLObjectType:
        # Check if it's a Graphene type
        if issubclass(object_type, graphene.ObjectType):
            return self.add_graphene_type(object_type)

        return self.from_object(object_type._type_definition)

    def from_type(self, type_: Any) -> GraphQLType:
        if issubclass(type_, BaseGrapheneType):
            return self.add_graphene_type(type_)
        return super().from_type(type_)


class GrapheneTypeMap(BaseGrapheneTypeMap):
    def __init__(self, strawberry_convertor, *args, **kwargs):
        self.strawberry_convertor = strawberry_convertor
        super().__init__(*args, **kwargs)

    def add_type(self, graphene_type):
        if hasattr(graphene_type, "_type_definition") or hasattr(
            graphene_type, "_enum_definition"
        ):
            return self.strawberry_convertor.from_type(graphene_type)

        # Special case decimal
        if isinstance(graphene_type, type) and issubclass(
            graphene_type, graphene.Decimal
        ):
            return self.strawberry_convertor.from_scalar(Decimal)

        if inspect.isfunction(graphene_type):
            graphene_type = graphene_type()
        if isinstance(graphene_type, graphene.List):
            return GraphQLList(self.add_type(graphene_type.of_type))
        if isinstance(graphene_type, graphene.NonNull):
            return GraphQLNonNull(self.add_type(graphene_type.of_type))
        try:
            name = graphene_type._meta.name
        except AttributeError as e:
            raise TypeError(
                f"Expected Graphene type, but received: {graphene_type}."
            ) from e
        graphql_type = self.get(name)
        if graphql_type:
            return graphql_type
        if issubclass(graphene_type, graphene.ObjectType):
            graphql_type = self.create_objecttype(graphene_type)
        elif issubclass(graphene_type, graphene.InputObjectType):
            graphql_type = self.create_inputobjecttype(graphene_type)
        elif issubclass(graphene_type, graphene.Interface):
            graphql_type = self.create_interface(graphene_type)
        elif issubclass(graphene_type, graphene.Scalar):
            graphql_type = self.create_scalar(graphene_type)
        elif issubclass(graphene_type, graphene.Enum):
            graphql_type = self.create_enum(graphene_type)
        elif issubclass(graphene_type, graphene.Union):
            graphql_type = self.construct_union(graphene_type)
        else:
            raise TypeError(
                f"Expected Graphene type, but received: {graphene_type}."
            )
        self[name] = graphql_type
        if not issubclass(graphene_type, graphene.Scalar):
            self.strawberry_convertor.type_map[name] = ConcreteType(
                definition=None, implementation=graphql_type
            )
        return graphql_type


class Schema(strawberry.Schema):
    def __init__(
        self,
        # TODO: can we make sure we only allow to pass something that has been decorated?
        query: Type,
        mutation: Optional[Type] = None,
        subscription: Optional[Type] = None,
        directives: Sequence[StrawberryDirective] = (),
        types=(),
        extensions: Sequence[Union[Type[Extension], Extension]] = (),
        execution_context_class: Optional[
            Type[GraphQLExecutionContext]
        ] = None,
        config: Optional[StrawberryConfig] = None,
        scalar_overrides: Optional[
            Dict[object, Union[ScalarWrapper, ScalarDefinition]]
        ] = None,
    ):
        self.extensions = extensions
        self.execution_context_class = execution_context_class
        self.config = config or StrawberryConfig()

        scalar_registry: Dict[
            object, Union[ScalarWrapper, ScalarDefinition]
        ] = {**DEFAULT_SCALAR_REGISTRY}
        if scalar_overrides:
            scalar_registry.update(scalar_overrides)

        self.schema_converter = GraphQLCoreConverter(
            self.config, scalar_registry
        )
        self.directives = directives

        query_type = self.schema_converter.from_object_type(query)
        mutation_type = (
            self.schema_converter.from_object_type(mutation)
            if mutation
            else None
        )
        subscription_type = (
            self.schema_converter.from_object_type(subscription)
            if subscription
            else None
        )

        graphql_directives = [
            self.schema_converter.from_directive(directive)
            for directive in directives
        ]

        graphql_types = []
        for type_ in types:
            graphql_type = self.schema_converter.from_object_type(type_)
            graphql_types.append(graphql_type)

        self._schema = GraphQLSchema(
            query=query_type,
            mutation=mutation_type,
            subscription=subscription_type if subscription else None,
            directives=specified_directives + graphql_directives,
            types=graphql_types,
        )

        # attach our schema to the GraphQL schema instance
        self._schema._strawberry_schema = self  # type: ignore

        # Validate schema early because we want developers to know about
        # possible issues as soon as possible
        errors = validate_schema(self._schema)
        if errors:
            formatted_errors = "\n\n".join(
                f"❌ {error.message}" for error in errors
            )
            raise ValueError(f"Invalid Schema. Errors:\n\n{formatted_errors}")

        self.query = self.schema_converter.type_map[query_type.name]

    def get_type_by_name(
        self, name: str
    ) -> Optional[
        Union[
            TypeDefinition, ScalarDefinition, EnumDefinition, StrawberryUnion
        ]
    ]:
        if name in self.schema_converter.type_map:
            return getattr(
                self.schema_converter.type_map[name], "definition", None
            )

        return None