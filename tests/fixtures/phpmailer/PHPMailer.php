<?php
// Test double: copied ONLY into a disposable test document root, never released.
namespace PHPMailer\PHPMailer;
#[\AllowDynamicProperties]
class PHPMailer
{
    const ENCRYPTION_SMTPS = 'ssl';
    public array $attachments = [];
    public array $headers = [];
    public function __construct($exceptions = true) {}
    public function isSMTP() {}
    public function getSMTPInstance() { return new \stdClass(); }
    public function isHTML($value) {}
    public function setFrom($email, $name) { $this->from = [$email, $name]; }
    public function addAddress($email, $name) { $this->recipient = [$email, $name]; }
    public function addReplyTo($email, $name) { $this->replyTo = [$email, $name]; }
    public function addCustomHeader($name, $value) { $this->headers[$name] = $value; }
    public function addAttachment($path, $name, $encoding, $mime) {
        $this->attachments[] = ['name' => $name, 'mime' => $mime, 'size' => filesize($path)];
    }
    public function send() {
        $directory = getenv('ORDER_TEST_MAIL_DIRECTORY');
        if (!$directory) throw new \RuntimeException('Test mail directory required');
        file_put_contents($directory . '/attempts', $this->MessageID . "\n", FILE_APPEND);
        if (is_file($directory . '/fail')) throw new \RuntimeException('Simulated SMTP failure');
        if (is_file($directory . '/fail-customer') && strpos($this->MessageID, '<order-recap-') === 0) {
            throw new \RuntimeException('Simulated customer SMTP failure');
        }
        file_put_contents($directory . '/' . bin2hex(random_bytes(8)) . '.json', json_encode([
            'from' => $this->from, 'to' => $this->recipient, 'replyTo' => $this->replyTo,
            'html' => $this->Body, 'text' => $this->AltBody, 'subject' => $this->Subject,
            'messageId' => $this->MessageID, 'attachments' => $this->attachments, 'headers' => $this->headers,
        ], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR));
        return true;
    }
}
