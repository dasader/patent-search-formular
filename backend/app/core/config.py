from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-2.0-flash"

    # KIPRIS
    kipris_api_key: str
    kipris_daily_limit: int = 100
    kipris_max_iterations: int = 2

    # PatentsView
    patentsview_api_key: str = ""
    patentsview_max_iterations: int = 3

    # Relevance evaluation thresholds
    relevance_min_good_ratio: float = 0.4    # 3점 이상 비율 >= 40%이면 통과
    relevance_max_noise_ratio: float = 0.3   # 1점 비율 <= 30%이면 통과

    # Pipeline
    pipeline_timeout: int = 300
    max_input_length: int = 5000

    # Paths
    data_dir: str = "./data"

    model_config = {"env_file": ["../.env", ".env"], "extra": "ignore"}


settings = Settings()
