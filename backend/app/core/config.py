from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-2.0-flash"

    # KIPRIS
    kipris_api_key: str
    kipris_monthly_limit: int = 1000
    kipris_max_iterations: int = 2

    # PatentsView
    patentsview_api_key: str = ""
    patentsview_max_iterations: int = 3

    # Pipeline
    pipeline_timeout: int = 180
    max_input_length: int = 5000

    # Paths
    data_dir: str = "./data"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
