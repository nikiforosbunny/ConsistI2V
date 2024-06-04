""" Entrypoint script for animation worker consuming RabbitMQ messages
"""

# native
import time
import logging
import base64
import os
from os.path import join
# local
from scripts import animate
from backend_utils.messaging import instantiate_broker
# third-party
from pymongo import MongoClient, errors

logging.basicConfig(level=logging.INFO)

device = os.environ.get("DEVICE", "cpu")
assert device in ["cpu", "cuda"], f"Unknown device: {device} -- expected 'cpu' or 'cuda'"
broker_type = os.environ.get("BROKER_TYPE", "rabbitmq")
db_host = os.environ.get("DB_HOST")
db_port = int(os.environ.get("DB_PORT", "27017"))

max_request_attempts = int(os.environ.get("MAX_REQUEST_ATTEMPTS", 3))

cfg = {

    'heartbeat': int(os.environ.get("HEARTBEAT", 1800)),
    'host': os.environ.get("BROKER_HOST", 'localhost'),
    'username': os.environ["BROKER_USER"],
    'password': os.environ["BROKER_PASSWORD"],
    'queue_name': 'animation'
}
broker = instantiate_broker(broker_type, cfg)

# mongo init
while True:
    try:
        mongo_client = MongoClient(db_host, db_port)
        logging.info(f"Connecting to mongo db @ {db_host} -- {db_port} ...")
        logging.info(f"Connected: {mongo_client.server_info()}")
        db = mongo_client['animation']
        images_db = db['images']
        animations_db = db['results']
        break
    except errors.ServerSelectionTimeoutError as e:
        logging.error(f"Failed to connect to mongo DB at host:[{db_host}], port: [{db_port}]: {e}")
        logging.error(f"Retrying in 5 seconds...")
        time.sleep(5)


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
    request = animations_db.find_one({"_id": task_id})

    status = request['status']
    if status in ('complete', 'failed'):
        logging.error(f"Received processing request for an animation task with status {status}: {task_id}")
        # done, don't requeue
        return True, False

    try:
        current_request_attempts = request.get('num_attempts', 0) + 1
        logging.info(f"Processing message -- request: {task_id}, attempt # {current_request_attempts} / {max_request_attempts}")
        # log processing attempt
        animations_db.update_one({'_id': task_id}, {'$set': {'status': 'processing', 'num_attempts': current_request_attempts}})

        # check id
        req_id = request.pop('_id')
        assert task_id == req_id, f"Message and db task id mismatch: {task_id} != {req_id}"

        # fetch input data from the entry
        submitted_by = request.pop('submitted_by')
        prompt = request.pop('prompt')
        prompt = prompt if prompt is not None else ''
        anim_format = request.get('animation_format', 'gif')

        # read and decode image from the images db
        image_id = request.pop('image_id')
        image_b64 = images_db.find_one({"_id": image_id})['image']
        image = base64.b64decode(image_b64)

        # write input image
        image_path = join(inputs_folder, f"{task_id}.svg")
        with open(image_path, "wb") as f:
            f.write(image)

        # write prompt file
        prompt_path = join(inputs_folder, f"{task_id}.prompt.txt")
        prompt_file_content = prompt_template.format(input_path=image_path, prompt_text=prompt)
        with open(prompt_path, "w") as f:
            f.write(prompt_file_content)

        # TODO: valid parameter filtering and anim. parameterization
        parameters = request.pop('parameters', {})

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

        # write result: animation data, complete status and initialize votes to 50 %
        with open(result_path, 'rb') as f:
            animation = f.read()
        animations_db.update_one({'_id': task_id}, {'$set': {'animation': animation, 'status': 'complete', 'votes': {submitted_by: 0.5}}})

        # success, don't requeue
        return True, False
    except Exception as exc:
        # log error to stdout and db
        error_msg = f"Failed to generate animation for request: {exc}"
        logging.error(error_msg)
        all_errors = request.get('errors', []) + [error_msg]
        animations_db.update_one({'_id': task_id}, {'$set': {'errors': all_errors}})

        # check if max number of attempts has been reach for the task
        reached_max_attempts = current_request_attempts == max_request_attempts
        if reached_max_attempts:
            # if max number of attempts reached, mark as failed and don't retry
            logging.error(f"Reached max number of attempts ({max_request_attempts}) without success for request: {task_id}")
            animations_db.update_one({'_id': task_id}, {'$set': {'status': 'failed'}})
        # else requeue to retry
        return False, not reached_max_attempts

def main():
    # Connect to RabbitMQ server
    broker.setup_connection()
    broker.listen(process_request)

if __name__ == "__main__":
    main()