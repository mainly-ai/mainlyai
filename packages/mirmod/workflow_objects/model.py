from mirmod.utils.logger import logger
from ..security.security_context import Security_context
from ..orm.base_orm import Base_object_ORM
import importlib.util
import sys
import json
from mirmod.execution_context import get_execution_context
from mirmod.platform_versions import PLATFORM_VERSION
import os
import copy


def _load_plugin(plugin_path, plugin_name):
    spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
    plugin_module = importlib.util.module_from_spec(spec)
    sys.modules[plugin_name] = plugin_module
    spec.loader.exec_module(plugin_module)
    return plugin_module


class model_card_api:
    def load_artefacts(self, destination_path: str = ""):
        """Load artefacts from the model card database and download to the local file system."""
        assert False, "load_artefacts() not implemented"

    def predict(self, features):
        """Make a prediction and return a result set"""
        assert False, "predict() not implemented"

    def train(
        self,
        features=None,
        labels=None,
        test_features=None,
        test_labels=None,
        callback_function=None,
    ):
        """Train the model and on every epoc call the callback function with the epoc number, loss and accuracy."""
        assert False, "train() not implemented"

    def save_artefacts(self, source_path: str = "", loss=0.0, nepochs=1):
        """Save artefacts to the model card database."""
        assert False, "save_artefacts() not implemented"

    def delete_artefacts(self):
        """Delete artefacts from the model card database. Note that this doesn't remove the model card entry."""
        assert False, "delete_artefacts() not implemented"

    def list_artefacts(self):
        """List all artefacts that are stored in the model card database."""
        assert False, "list_artefacts() not implemented"

    def create_new_model_impl(self, params: dict):
        """Every model frame work has their own unique way to create model instances. The parameters for creating the model are passed in as a dictionary."""
        assert False, "create_new_model_impl() not implemented"

    def get_model_implementation(self):
        """Returns the underlying model implementation which allows for direct access to it. The type of this object is determined by the underlying framework used."""
        assert False, "get_model_implementation() not implemented"

    def set_model_card(self, model):
        """Sets the model card object."""
        assert False, "set_model_card() not implemented"

    def get_optimizer(self):
        """Returns the optimizer used for training the model."""
        assert False, "get_optimizer() not implemented"

    def set_optimizer(self, i):
        """Sets the optimizer used for training the model."""
        assert False, "set_optimizer() not implemented"

    def get_criterion(self):
        """Returns the criterion used for estimating loss."""
        assert False, "get_criterion() not implemented"

    def set_criterion(self, i):
        """Sets the criterion used for estimating loss."""
        assert False, "set_criterion() not implemented"


class Model(Base_object_ORM, model_card_api):
    # Model table has alias t
    sql_object_ORM = {
        "id": "t.id as id",
        "model_type": "t.model_type as model_type",
        "miranda_version": "t.miranda_version as miranda_version",
        "hardware": "t.hardware as hardware",
        "load_url": "t.load_url as load_url",
        "save_url": "t.save_url as save_url",
        "files": "t.files as files",
        "authors": "t.authors as authors",
        "license": "t.license as license",
        "feature_labels": "t.feature_labels as feature_labels",
        "prediction_labels": "t.prediction_labels as prediction_labels",
        "feature_units": "t.feature_units as feature_units",
        "prediction_units": "t.prediction_units as prediction_units",
        "loss": "t.loss as loss",
        "accuracy": "t.accuracy as accuracy",
        "precision": "t.precision as `precision`",
        "recall": "t.recall as recall",
        "knowledge_object_id": "t.knowledge_object_id as knowledge_object_id",
        "workflow_state": "t.workflow_state as workflow_state",
    }

    sql_object_ORM.update(Base_object_ORM.metadata)

    def __init__(
        self, sc: Security_context, id=-1, metadata_id=None, user_id=-1, model_type=None
    ):
        self.default_value = {
            "id": -1,
            "metadata_id": -1,
            "model_type": "PYTORCH",
            "miranda_version": PLATFORM_VERSION,
            "hardware": '["CPU"]',
            "load_url": "",
            "save_url": "",
            "files": "[]",
            "authors": "[]",
            "license": "",
            "feature_labels": "[]",
            "prediction_labels": "[]",
            "feature_units": "[]",
            "prediction_units": "[]",
            "loss": 0.0,
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "knowledge_object_id": -1,
            "workflow_state": "UNINITIALIZED",
        }
        self.has_loaded_artefacts = False
        self.id = id
        self.sctx = sc
        self.create_mapping(self.sql_object_ORM, "model")
        self.model_type = model_type
        self.model_impl: model_card_api = None
        if metadata_id is not None:
            self._load_from_metadata_id(sc, metadata_id, user_id=user_id)
            # logger.info("Loaded ML_model object with metadata id: " + str(metadata_id))
        elif id != -1:
            self._load_from_id(sc, self.id)
            # logger.info("Loaded ML_model object with id: " + str(id))
        self.params = None

        try:
            ecx = get_execution_context()
            self.storage_policy = ecx.get_storage_policy()
        except Exception as e:
            logger.error(f"Error getting storage policy: {e}")
            self.storage_policy = None

    def load_artefacts(self, destination_path: str = ""):
        """Load artefacts from the model card database and download to the local file system."""
        if self.has_loaded_artefacts:
            print("|=> load_artefact: Artefacts already loaded.")
            return
        if self.model_impl is None:
            print("|=> load_artefact: No model implementation has been specified.")
            return
        self.has_loaded_artefacts = True
        if self.storage_policy is not None:
            files = json.loads(self.files)
            for f in files:
                self.storage_policy.load_file(os.path.join(destination_path, f))
        self.model_impl.load_artefacts(destination_path)

    def predict(self, features):
        """Make a prediction and return a result set"""
        assert self.has_loaded_artefacts, (
            "Artefacts must be loaded before making a prediction."
        )
        return self.model_impl.predict(features)

    def train(
        self,
        features=None,
        labels=None,
        test_features=None,
        test_labels=None,
        callback_function=None,
    ):
        """Train the model and on every epoch call the callback function with the epoch number, loss and accuracy.
        For every epoch the call_backfunction is called with the following parameters:
        callback_function(epoch, loss, accuracy)
        """
        ret = self.model_impl.train(
            features, labels, test_features, test_labels, callback_function
        )
        self.has_loaded_artefacts = True
        return ret

    def save_artefacts(self, source_path: str = "", loss=0.0, nepochs=1):
        """Save artefacts to the model card database."""
        # First we call the model implementation to save any artefacts to the local file system
        self.model_impl.save_artefacts(source_path, loss=loss, nepochs=nepochs)
        # We ask the model implementation to supply us with the filenames of the artefacts
        files = self.model_impl.list_artefacts()
        self.files = json.dumps(files)
        if files is None:
            return
        for f in files:
            # We use the storage policy to save the artefacts to a persistent storage
            self.storage_policy.save_file(os.path.join(source_path, f))
            self.load_url = self.storage_policy.load_url
            self.save_url = self.storage_policy.save_url
        # We update the database with the new list of files
        self.update(self.sctx)

    def copy_to(self, new_name: str, new_description: str, path=""):
        self.load_artefacts()
        # get the parameters needed to recreate the model implementation
        try:
            id, _ = next(find_model_id_by_name(self.sctx, new_name))
            new_model: Model = Model(self.sctx, id=id)
            new_model.has_loaded_artefacts = True
        except StopIteration:
            new_model: Model = Model(self.sctx, id=-1)
            with self.sctx.connect() as con:
                id, _ = new_model.create(con, new_name, new_description)
                new_model = Model(self.sctx, id=id)
            assert new_model.id != -1, "Target '{}' could not be created.".format(
                new_name
            )
        new_model.model_impl = copy.copy(self.model_impl)
        new_model.model_impl.set_model_card(new_model)
        self.model_impl.save_artefacts(
            path
        )  # make sure the artefacts are saved to local disk
        for f1, f2 in zip(
            self.model_impl.list_artefacts(), new_model.model_impl.list_artefacts()
        ):
            print("cp {} {}".format(os.path.join(path, f1), os.path.join(path, f2)))
            os.system("cp {} {}".format(os.path.join(path, f1), os.path.join(path, f2)))
        new_model.has_loaded_artefacts = True
        if self.storage_policy is not None:
            for f in new_model.model_impl.list_artefacts():
                self.storage_policy.save_file(os.path.join(path, f))
            files = new_model.model_impl.list_artefacts()
            new_model.files = json.dumps(files)
        new_model.set_feature_labels(self.get_feature_labels())
        new_model.set_prediction_labels(self.get_prediction_labels())
        new_model.set_feature_units(self.get_feature_units())
        new_model.set_prediction_units(self.get_prediction_units())
        new_model.update(self.sctx)
        return new_model

    def get_model_implementation(self):
        # This actually returns the implementation of the model of the instance of the framework, so effectively the implementation of the implementation.
        return self.model_impl.get_model_implementation()

    def delete_artefacts(self):
        """Delete artefacts from the model card database. This call does nothing for the local files."""
        self.delete_artefacts()

    def get_feature_labels(self):
        if self.feature_labels is None:
            return []
        if isinstance(self.feature_labels, list):
            return self.feature_labels
        return json.loads(self.feature_labels)

    def set_feature_labels(self, labels):
        if isinstance(labels, list):
            self.feature_labels = json.dumps(labels)
        elif isinstance(labels, str):
            self.feature_labels = labels
        else:
            raise Exception("Labels must be a list or a string")

    def set_prediction_labels(self, labels):
        if isinstance(labels, list):
            self.prediction_labels = json.dumps(labels)
        elif isinstance(labels, str):
            self.prediction_labels = labels
        else:
            raise Exception("Labels must be a list or a string")

    def get_prediction_labels(self):
        if self.prediction_labels is None:
            return []
        if isinstance(self.prediction_labels, list):
            return self.prediction_labels
        return json.loads(self.prediction_labels)

    def get_feature_units(self):
        if self.feature_units is None:
            return []
        if isinstance(self.feature_units, list):
            return self.feature_units
        return json.loads(self.feature_units)

    def set_feature_units(self, units):
        if isinstance(units, list):
            self.feature_units = json.dumps(units)
        elif isinstance(units, str):
            self.feature_units = units
        else:
            raise Exception("Units must be a list or a string")

    def set_prediction_units(self, units):
        if isinstance(units, list):
            self.prediction_units = json.dumps(units)
        elif isinstance(units, str):
            self.prediction_units = units
        else:
            raise Exception("Units must be a list or a string")

    def get_prediction_units(self):
        if self.prediction_units is None:
            return []
        if isinstance(self.prediction_units, list):
            return self.prediction_units
        return json.loads(self.prediction_units)

    def get_optimizer(self):
        """Returns the optimizer used for training the model."""
        return self.model_impl.get_optimizer()

    def set_optimizer(self, i):
        """Sets the optimizer used for training the model."""
        self.model_impl.set_optimizer(i)

    def get_criterion(self):
        """Returns the criterion used for estimating loss."""
        return self.model_impl.get_criterion()

    def set_criterion(self, i):
        """Sets the criterion used for estimating loss."""
        self.model_impl.set_criterion(i)


# ---------------- END class Model ----------------


def find_model_id_by_name(sc: Security_context, name: str):
    with sc.connect() as conn:
        with conn.cursor() as cur:
            sql = "SELECT t.id, t.model_type FROM v_model t WHERE t.name = %s"
            cur.execute(sql, (name,))
            rows = cur.fetchall()
            for row in rows:
                yield row


def create_or_update_modelcard(
    sctx,
    name,
    description,
    model_type="PYTORCH",
    miranda_version=PLATFORM_VERSION,
    hardware=["GPU"],
    authors="MainlyAI",
    license="",
    prediction_units=[],
    feature_units=[],
    prediction_labels=[],
):
    """Attempt to create a new model card. If a model card with the same name already exists it is loaded, modified and returned."""
    found = False
    model_card = Model(sctx, id=-1, model_type="PYTORCH")
    for m in find_model_id_by_name(sctx, name):
        if m[1] != model_type:
            raise Exception(
                "Model card with name "
                + name
                + " already exists with a different model type"
            )
        print(
            "Found an existing model using name '{}' (id={}). Load all the data from the database.".format(
                name, m[0]
            )
        )
        model_card = Model(sctx, id=m[0])
        assert id != -1, (
            "Model card with name "
            + name
            + " was found with id = {} but could not be loaded.".format(m[0])
        )
        found = True
        break

    if not found:
        with sctx.connect() as con:
            model_id, metadata_id = model_card.create(
                con, name, description, model_type=model_type
            )
            con.commit()
            model_card = Model(sctx, id=model_id)
            print(
                "Created a new model card entry with ID: {} ({})".format(
                    model_id, metadata_id
                )
            )
    model_card.authors = authors
    model_card.model_type = model_type
    model_card.miranda_version = miranda_version
    model_card.hardware = json.dumps(hardware)
    model_card.license = license
    model_card.prediction_units = json.dumps(prediction_units)
    model_card.feature_units = json.dumps(feature_units)
    model_card.prediction_labels = json.dumps(prediction_labels)
    model_card.update(sctx)
    return model_card
