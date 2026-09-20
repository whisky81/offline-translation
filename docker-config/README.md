Cau hinh Docker CLI rieng cua project, co lap khoi `~/.docker`.

Ly do: `~/.docker/config.json` cua may nay co
  "credsStore": "desktop"        -> moi lenh docker goi docker-credential-desktop,
                                    that bai khi Docker Desktop khong chay
  "currentContext": "desktop-linux" -> tro vao VM cua Desktop
  "plugins": { ... hooks ... }   -> plugin Desktop chen hook vao `compose up`, `logs`...

Moi script trong project deu dat DOCKER_CONFIG tro vao thu muc nay, nen:
  - khong dung credential helper (image cong khai, khong can dang nhap)
  - context la `default`, va DOCKER_HOST con ep thang vao /var/run/docker.sock
  - `cli-plugins/` symlink toi dung binary cua docker-ce

Khong sua `~/.docker/config.json` — Docker Desktop cua ban van nguyen ven.
