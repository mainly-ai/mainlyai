from mirmod import miranda
from .api import StorageInterface
from .vault import VaultStorageInterface
import os

def get_storage_interface_from_ecx(ecx) -> StorageInterface:
	sc = ecx.get_security_context()
	ko = ecx.get_knowledge_object()
	sp = list(miranda.find_children(sc, ko.metadata_id, wob_type='STORAGE_POLICY'))[0]

	if sp.storage_type == "VAULT":
		return VaultStorageInterface(sc, sp, verify_ssl=os.environ.get("I_AM_IN_AN_ISOLATED_AND_SAFE_CONTEXT") == "1")
	else:
		raise Exception(f"Storage type {sp.storage_type} is not implemented")
