import asyncio
import os
from decimal import Decimal
from textwrap import dedent

import django
import graphene
import strawberry

from strawberry_graphene.extension import SyncToAsync
from strawberry_graphene.schema import Schema

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.app.settings')

django.setup()

from django.contrib.auth.models import User as DjangoUser


def test_convert_graphene_basic():
    class Query(graphene.ObjectType):
        hello = graphene.String(default_value="World")

    schema = Schema(query=Query)

    expected = dedent(
        """\
        type Query {
          hello: String
        }
        """
    ).strip()

    assert str(schema) == expected

    result = schema.execute_sync("{ hello }")
    assert not result.errors
    assert result.data == {"hello": "World"}


def test_convert_graphene_more():
    class GraphQLFramework(graphene.Interface, ):
        id = graphene.ID()
        graphql_core = graphene.String()

    class GrapheneV2(graphene.ObjectType):
        class Meta:
            interfaces = (GraphQLFramework,)

        def resolve_id(root, info):
            return "1"

        def resolve_graphql_core(root, info):
            return "legacy"

    class GrapheneV3(graphene.ObjectType):
        class Meta:
            interfaces = (GraphQLFramework,)

        def resolve_id(root, info):
            return "2"

        def resolve_graphql_core(root, info):
            return "v3"

    class Strawberry(graphene.ObjectType):
        class Meta:
            interfaces = (GraphQLFramework,)

        def resolve_id(root, info):
            return "3"

        def resolve_graphql_core(root, info):
            return "v3"

    lst_qrcodes_interface_types = [GrapheneV2, GrapheneV3, Strawberry]

    class PetType(graphene.Enum):
        DOG = "dog"
        CAT = "cat"

    class Pet(graphene.ObjectType):
        name = graphene.String()
        pet_type = graphene.Field(PetType)

    class User(graphene.ObjectType):
        id = graphene.ID()
        pets = graphene.List(Pet)
        previous_framework = graphene.Field(GraphQLFramework)
        current_framework = graphene.Field(GraphQLFramework)

        def resolve_pets(root, info):
            return [
                {"name": "Lucky", "pet_type": PetType.DOG},
                {"name": "Spot", "pet_type": PetType.DOG},
            ]

        def resolve_previous_framework(root, info):
            return GrapheneV2()

        def resolve_current_framework(root, info):
            return Strawberry()

    class Query(graphene.ObjectType):
        user = graphene.Field(User, id=graphene.ID(required=True))

        def resolve_user(self, info, id):
            return User(id=id)

    schema = Schema(query=Query, types=lst_qrcodes_interface_types)

    expected = dedent(
        """\
        interface GraphQLFramework {
          id: ID
          graphqlCore: String
        }
        
        type GrapheneV2 implements GraphQLFramework {
          id: ID
          graphqlCore: String
        }
        
        type GrapheneV3 implements GraphQLFramework {
          id: ID
          graphqlCore: String
        }
        
        type Pet {
          name: String
          petType: PetType
        }
        
        enum PetType {
          DOG
          CAT
        }
        
        type Query {
          user(id: ID!): User
        }
        
        type Strawberry implements GraphQLFramework {
          id: ID
          graphqlCore: String
        }
        
        type User {
          id: ID
          pets: [Pet]
          previousFramework: GraphQLFramework
          currentFramework: GraphQLFramework
        }
        """
    ).strip()

    print(str(schema))

    assert str(schema) == expected

    result = schema.execute_sync(
        """
        {
          user(id: "test") {
            id
            pets {
              name
              petType
            }
            previousFramework {
              id
              graphqlCore
            }
            currentFramework {
              id
              graphqlCore
            }            
          }
        }
    """
    )
    assert not result.errors
    assert result.data == {
        "user": {
            "id": "test",
            "pets": [
                {
                    "name": "Lucky",
                    "petType": "DOG",
                },
                {
                    "name": "Spot",
                    "petType": "DOG",
                },
            ],
            "previousFramework": {
                "id": "1",
                "graphqlCore": "legacy",
            },
            "currentFramework": {
                "id": "3",
                "graphqlCore": "v3",
            },
        }
    }


def test_decimal_type():
    class GrapheneType(graphene.ObjectType):
        another_decimal = graphene.Decimal()

    @strawberry.type
    class Query:
        a_decimal: Decimal
        another_type: GrapheneType

    schema = Schema(query=Query)

    expected = dedent(
        """\
        \"""Decimal (fixed-point)\"""
        scalar Decimal

        type GrapheneType {
          anotherDecimal: Decimal
        }

        type Query {
          aDecimal: Decimal!
          anotherType: GrapheneType!
        }
        """
    ).strip()

    assert str(schema) == expected


def test_graphene_type_resolving_strawberry_type():
    @strawberry.type
    class Pet:
        name: str

    class User(graphene.ObjectType):
        pet = graphene.Field(Pet)

        def resolve_pet(self, info):
            return Pet(name="Spot")

    @strawberry.type
    class Query:
        @strawberry.field
        def user(self, info) -> User:
            return User()

    schema = Schema(Query)

    expected = dedent(
        """\
        type Pet {
          name: String!
        }

        type Query {
          user: User!
        }

        type User {
          pet: Pet
        }
        """
    ).strip()
    assert str(schema) == expected

    result = schema.execute_sync(
        """
        {
            user {
                pet {
                    name
                }
            }
        }
        """
    )
    assert not result.errors
    assert result.data == {"user": {"pet": {"name": "Spot"}}}


def test_mutation():
    @strawberry.type
    class User:
        username: str

    class AddUser(graphene.Mutation):
        class Arguments:
            username = graphene.String(required=True)

        user = graphene.Field(User)

        def mutate(self, info, username):
            return AddUser(user=User(username))

    class Mutation(graphene.ObjectType):
        add_user = AddUser.Field()

    @strawberry.type
    class Query:
        hi: str

    schema = Schema(Query, mutation=Mutation)

    expected = dedent(
        """\
        type AddUser {
          user: User
        }

        type Mutation {
          addUser(username: String!): AddUser
        }

        type Query {
          hi: String!
        }

        type User {
          username: String!
        }
        """
    ).strip()
    assert str(schema) == expected

    result = schema.execute_sync(
        """
        mutation AddUser {
            addUser(username: "jkimbo") {
                user {
                    username
                }
            }
        }
        """
    )
    assert not result.errors
    assert result.data == {"addUser": {"user": {"username": "jkimbo"}}}


def test_mutation_async():
    @strawberry.type
    class User:
        username: str

    class AddUser(graphene.Mutation):
        class Arguments:
            username = graphene.String(required=True)

        user = graphene.Field(User)

        def mutate(self, info, username):
            # create a new Django User
            user = DjangoUser.objects.get_or_create(email='user@email.fake')
            return AddUser(user=User(username))

    class Mutation(graphene.ObjectType):
        add_user = AddUser.Field()

    @strawberry.type
    class Query:
        hi: str

    schema = Schema(Query, mutation=Mutation, extensions=[SyncToAsync(), ], )

    expected = dedent(
        """\
        type AddUser {
          user: User
        }

        type Mutation {
          addUser(username: String!): AddUser
        }

        type Query {
          hi: String!
        }

        type User {
          username: String!
        }
        """
    ).strip()
    assert str(schema) == expected

    result = asyncio.run(schema.execute(
        """
        mutation AddUser {
            addUser(username: "jkimbo") {
                user {
                    username
                }
            }
        }
        """
    ))
    assert not result.errors
    assert result.data == {"addUser": {"user": {"username": "jkimbo"}}}
