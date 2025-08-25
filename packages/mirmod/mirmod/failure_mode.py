from typing import Callable, Dict
import functools


class FailureMode(Exception):
    def __init__(self, mode: str, original_exception: Exception):
        self.mode = mode
        self.original_exception = original_exception
        super().__init__(
            f"|=> ERROR: Failure mode '{mode}' occurred: {str(original_exception)}"
        )


class RecoveryStrategy:
    def __init__(self, strategy: Callable):
        self.strategy = strategy

    def execute(self, *args, **kwargs):
        return self.strategy(*args, **kwargs)


class FailureModeHandler:
    def __init__(self, failure_modes: Dict[str, RecoveryStrategy]):
        self.failure_modes = failure_modes

    def __call__(self, func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                for mode, recovery_strategy in self.failure_modes.items():
                    if mode.lower() in str(e).lower():
                        if mode.startswith("|=>"):
                            mode = mode[4:]
                        print(f"|=> Attempting to recover from failure mode: {mode}")
                        try:
                            result = recovery_strategy.execute(*args, **kwargs)
                            print(f"|=> Recovery successful for {mode}")
                            return result
                        except Exception as recovery_error:
                            err = str(recovery_error)
                            err = err.replace("|=>", "")
                            print(f"|=> Recovery failed for {mode}: {err}")
                            raise FailureMode(mode, e)
                raise FailureMode("|=> ERROR: Unexpected failure", e)

        return wrapper
