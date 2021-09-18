# Strawberry/Graphene interoperability

Provide a way to use both Strawberry and Graphene types in the same schema.

**Note:** Requires Graphene v3

**⚠️ This library is experimental**

## Setup

1. Install library
```
pip install git+https://github.com/jkimbo/strawberry-graphene.git
```

2. Replace the Graphene Schema with the custom schema

```diff
 import graphene
+from strawberry_graphene import Schema


 class Query(graphene.ObjectType):
@@ -8,4 +9,4 @@ class Query(graphene.ObjectType):
         return "World"


-schema = graphene.Schema(query=Query)
+schema = Schema(query=Query)
```

3. Start converting your types

```diff
 import graphene
+import strawberry

-class User(graphene.ObjectType):
-    name = graphene.String()
-    age = graphene.Int()
+
+@strawberry.type
+class User:
+    name: str
+    age: int
```
