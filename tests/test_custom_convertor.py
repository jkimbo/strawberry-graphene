from textwrap import dedent
from decimal import Decimal
import graphene
import strawberry

from main.schema import Schema


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
    class PetType(graphene.Enum):
        DOG = "dog"
        CAT = "cat"

    class Pet(graphene.ObjectType):
        name = graphene.String()
        pet_type = graphene.Field(PetType)

    class User(graphene.ObjectType):
        id = graphene.ID()
        pets = graphene.List(Pet)

        def resolve_pets(root, info):
            return [
                {"name": "Lucky", "pet_type": PetType.DOG},
                {"name": "Spot", "pet_type": PetType.DOG},
            ]

    class Query(graphene.ObjectType):
        user = graphene.Field(User, id=graphene.ID(required=True))

        def resolve_user(self, info, id):
            return User(id=id)

    schema = Schema(query=Query)

    expected = dedent(
        """\
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

        type User {
          id: ID
          pets: [Pet]
        }
        """
    ).strip()

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


# TODO
# test mutations
# test graphene type referring to Strawberry type
# test resolving graphene type from Strawberry type
