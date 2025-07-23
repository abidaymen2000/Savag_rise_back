# app/models/utils.py

from bson import ObjectId
from pydantic_core import PydanticCustomError
# on pioche core_schema dans l’implémentation interne
from pydantic._internal._schema_generation_shared import core_schema


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source, handler):
        """
        Schéma interne Pydantic : on lui dit “valide via cls.validate”
        """
        return core_schema.no_info_plain_validator_function(cls.validate)

    @classmethod
    def __get_pydantic_json_schema__(cls, _core_schema, _handler=None):
        """
        Schéma JSON/OpenAPI : on l’expose comme un string
        """
        return {"type": "string", "format": "object-id"}

    @classmethod
    def validate(cls, v):
        """
        Validation runtime : accepte un ObjectId ou une string valide
        """
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise PydanticCustomError("value_error.objectid", "Invalid ObjectId")
        return ObjectId(v)
