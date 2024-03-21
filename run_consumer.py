""" Entrypoint for animation worker consuming RabbitMQ messages
"""

# native
import logging
import base64
import os
from os.path import join
# local
from scripts import animate
from messaging import instantiate_broker
# third-party
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)

device = os.environ.get("DEVICE", "cpu")
assert device in ["cpu", "cuda"], f"Unknown device: {device} -- expected 'cpu' or 'cuda'"
broker_type = os.environ.get("BROKER_TYPE", "rabbitmq")
db_host = os.environ.get("DB_HOST")
db_port = int(os.environ.get("DB_PORT", "27017"))
heartbeat = int(os.environ.get("HEARTBEAT", 1800))
broker = instantiate_broker(broker_type, {'heartbeat': heartbeat})

# mongo init
mongo_client = MongoClient(db_host, db_port)
logging.info(f"Connecting to mongo db @ {db_host} -- {db_port} ...")
logging.info(f"Connected: {mongo_client.server_info()}")
db = mongo_client['animation']
db_collection = db['results']


# set the expected prompt template, formattable
# with request data
prompt_template = """
seeds: random

prompts:
  - "{prompt_text}"

n_prompts:
  - ""

path_to_first_frames:
  - "{input_path}"
"""

# worker io folders
inputs_folder = "inputs"
outputs_folder = "outputs"
os.makedirs(inputs_folder, exist_ok=True)
os.makedirs(outputs_folder, exist_ok=True)

def base64_to_bytes(b64: str):
    return base64.b64decode(b64)

def process_request(body: str):
    """Method to process a request

    Args:
        body (str): The request input, as json-dumped string

    Returns:
        tuple: A tuple of two booleans. The first is whether the request was successfully processed.
        The second is whether the request should be re-queued to try again.
    """
    # message is the task id to process -- retrieve
    task_id = body
    request = db_collection.find_one({"id": task_id})
    if request['status'] == 'complete':
        logging.error(f"Received processing request for an already completed animation task: {request['id']}")
        return True, False


    try:
        logging.info(f"Processing message -- request: {request['id']}")
        db_collection.update_one({'id': task_id}, {'$set': {'status': 'processing'}})

        req_id = request.pop('id')
        assert task_id == req_id, f"Message and db task id mismatch: {task_id} != {req_id}"

        prompt = request.pop('prompt')
        image_b64 = request.pop("image")
        image = base64.b64decode(image_b64)
        anim_format = request.get('animation_format', 'gif')

        # write input image
        image_path = join(inputs_folder, f"{task_id}.png")
        with open(image_path, "wb") as f:
            f.write(image)

        # write prompt file
        prompt_path = join(inputs_folder, f"{task_id}.prompt.txt")
        prompt_file_content = prompt_template.format(input_path=image_path, prompt_text=prompt)
        with open(prompt_path, "w") as f:
            f.write(prompt_file_content)

        animation_args = {
            "inference_config": "configs/inference/inference_rest.yaml",
            "prompt_config": prompt_path,
            "format": anim_format,
            "output_name": task_id,
            "output_folder": outputs_folder,
            "device": device,
            "only_output_animation": 1,
            "disable_metadata_in_animation_name": 1
        }

        # processing
        # ----------
        animate.call_module(animation_args)
        # ----------
        # # read result, write to db
        result_path = join(outputs_folder, f"{task_id}.{anim_format}")

        # dummy processing -- testing
        # -----------------
        # import time
        # logging.info("Starting processing...")
        # time.sleep(25)
        # logging.info("Finished.")
        # result_path = image_path
        # -----------------

        # update request
        with open(result_path, 'rb') as f:
            animation = f.read()
        db_collection.update_one({'id': task_id}, {'$set': {'animation': animation, 'status': 'complete'}})

        # success
        return True, False
    except Exception as e:
        logging.error(f"Worker failed to generate animation for request: {e}")
        # failure, requeue
        return False, True

def main():
    # Connect to RabbitMQ server
    broker.listen(process_request)

if __name__ == "__main__":
    main()