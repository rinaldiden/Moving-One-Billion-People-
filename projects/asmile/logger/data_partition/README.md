# Creare la partizione dati /data sulla SD (shrink rootfs)

Trasforma il layout `boot + rootfs(tutta la SD)` in `boot + rootfs 19G + /data 96G`,
senza reflash. **Rischioso** (resize offline) — vedi backup/restore prima.

## Procedura (testata 2026-10-29 su asmile-logger)

1. **Overlay OFF** (serve root rw per fstab/initramfs):
   `sudo raspi-config nonint disable_overlayfs && sudo reboot`

2. **Hook initramfs** (porta resize2fs/parted/e2fsck/mkfs nell'initramfs e fa il
   resize del FILESYSTEM offline, con p2 smontata):
   ```
   sudo install -m0755 asmile_resize.hook     /etc/initramfs-tools/hooks/asmile_resize
   sudo install -m0755 asmile_resize.premount /etc/initramfs-tools/scripts/init-premount/asmile_resize
   sudo update-initramfs -u
   echo "LABEL=data /data ext4 defaults,noatime,nofail 0 2" | sudo tee -a /etc/fstab
   sudo mkdir -p /data
   sudo reboot      # il premount fa: e2fsck + resize2fs p2 -> 18G
   ```
   NB: nel premount il `parted resizepart` FALLISCE (parted fa 2 domande interattive
   che `-s` non auto-conferma) → si ripiega sul boot normale (nessun danno). Il fs
   e' comunque gia' a 18G. Il resto della partizione si fa dal sistema vivo (passo 3).

3. **Shrink partizione + crea p3, DAL SISTEMA VIVO** (fs gia' 18G = sicuro):
   ```
   printf "Yes\nYes\n" | sudo parted ---pretend-input-tty /dev/mmcblk0 unit MiB resizepart 2 20000
   sudo parted -s /dev/mmcblk0 unit MiB mkpart primary ext4 20001 100%
   sudo partx -a -n 3 /dev/mmcblk0; sudo partprobe /dev/mmcblk0
   sudo mkfs.ext4 -F -L data /dev/mmcblk0p3
   sudo mount /data && sudo mkdir -p /data/recordings
   ```

4. **Overlay ON** con `recurse=0` (ALTRIMENTI overlaya anche /data → video in RAM!):
   ```
   sudo sed -i 's|overlayroot=tmpfs|overlayroot=tmpfs:recurse=0|' /boot/firmware/cmdline.txt
   # (se non presente, enable_overlayfs prima, poi aggiungi :recurse=0)
   sudo raspi-config nonint enable_overlayfs   # se overlay non ancora attivo
   sudo reboot
   ```
   Verifica: `mount | grep /data` → `/dev/mmcblk0p3 on /data type ext4 (rw)`.
