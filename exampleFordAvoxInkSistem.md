shell_command:
    davoxink_immage: 'curl --max-time 60 -X POST http://192.168.XXX.XXX/api/image -F "file=@{{ path }}"'
service: shell_command.davoxink_immage
    data:
          path: "{{ states('sensor.weasley_clock_image_path') }}"
rest_command: 
    davoxink_text:
    url: "http://192.168.XXX.XXX/api/text"
    method: POST
    headers:
      Content-Type: "application/json"
    payload: "{{ states('input_text.testo_notifica') }}"
    timeout: 60
