import threading

# Use thread-local storage at the module level to hold the context for each thread
_thread_local_storage = threading.local()


class Execution_context_api:
    def enable_debug_mode(self):
        pass

    def get_current_wob_metadata_id(self):
        pass

    def get_current_wob(self):
        pass

    def get_security_context(self):
        pass

    def get_storage_policy(self):
        pass

    def set_storage_policy(self, ob):
        pass

    def get_storage_interface(self):
        pass

    def get_knowledge_object(self):
        pass

    def get_inbound_message(self):
        pass

    def get_docker_job(self):
        pass

    def get_wob_file_template_path(self):
        pass

    def get_name(self):
        """Returns the name of the current WOB"""
        pass

    def execute_wob(self, wob):
        """Execute (or reexecute) the WOB using the current execution context."""
        pass

    def get_requirements(self):
        """Return the list of python module dependencies"""
        pass

    def set_requirements(self, r):
        """Sets the list of python module dependencies which must be installed before execution."""
        pass

    def get_global_context(self):
        pass

    def get_process_context(self):
        pass


def get_execution_context() -> Execution_context_api:
    """Gets the execution context specific to the current thread.
    Raises AttributeError if no context is set for the current thread."""
    try:
        return _thread_local_storage.current_context
    except AttributeError:
        raise RuntimeError("Execution context not set for the current thread.")


def set_current_execution_context(context):
    """Sets the execution context for the current thread."""
    _thread_local_storage.current_context = context
