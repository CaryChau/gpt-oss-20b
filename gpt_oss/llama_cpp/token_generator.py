import requests


class TokenGenerator:
    def __init__(
        self,
        encoding,
        base_url="http://127.0.0.1:9931",
        timeout=(10, None),
    ):
        self.encoding = encoding
        self.url = f"{base_url.rstrip('/')}/completion"
        self.timeout = timeout
        self.session = requests.Session()

    def generate(
        self,
        prompt_tokens: list[int],
        stop_tokens: list[int] | None = None,
        temperature: float = 1.0,
        max_tokens: int = 0,
        return_logprobs: bool = False,
    ):
        # Convert Harmony stop token IDs into their
        # corresponding special-token strings.
        stop_map = {}

        if stop_tokens:
            for token_id in stop_tokens:
                token_text = self.encoding.decode([token_id])

                if not token_text:
                    raise ValueError(
                        f"Cannot decode stop token: {token_id}"
                    )

                stop_map[token_text] = token_id

        payload = {
            "prompt": [int(t) for t in prompt_tokens],
            "temperature": temperature,
            "n_predict": max_tokens if max_tokens > 0 else -1,
            "return_tokens": True,
            "cache_prompt": True,
            "stream": False,
        }

        if stop_map:
            payload["stop"] = list(stop_map.keys())

        if return_logprobs:
            payload["n_probs"] = 1

        response = self.session.post(
            self.url,
            json=payload,
            timeout=self.timeout,
        )

        response.raise_for_status()
        data = response.json()

        token_ids = data.get("tokens", [])
        probabilities = data.get(
            "completion_probabilities", []
        )

        if not isinstance(token_ids, list):
            raise RuntimeError(
                "llama.cpp did not return token IDs"
            )

        # Yield the actual generated token IDs.
        for index, token_id in enumerate(token_ids):
            token_id = int(token_id)

            if return_logprobs:
                logprob = None

                if index < len(probabilities):
                    item = probabilities[index]

                    if item.get("id") == token_id:
                        logprob = item.get("logprob")

                yield (token_id, logprob)

            else:
                yield token_id

            # Preserve the original stop-token behavior.
            if stop_tokens and token_id in stop_tokens:
                return

        # llama.cpp excludes the stopping string from
        # response content. Restore its Harmony token ID.
        stopping_word = data.get("stopping_word", "")
        stopping_token = stop_map.get(stopping_word)

        if stopping_token is not None:
            if not token_ids or int(token_ids[-1]) != stopping_token:
                if return_logprobs:
                    yield (stopping_token, None)
                else:
                    yield stopping_token
